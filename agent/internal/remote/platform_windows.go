//go:build windows

package remote

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/binary"
	"fmt"
	"image"
	"image/jpeg"
	"log"
	"os"
	"sync"
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

// ─── DLL / proc handles ───────────────────────────────────────────────────────

var (
	user32   = windows.NewLazySystemDLL("user32.dll")
	gdi32    = windows.NewLazySystemDLL("gdi32.dll")
	kernel32 = windows.NewLazySystemDLL("kernel32.dll")
	advapi32 = windows.NewLazySystemDLL("advapi32.dll")
	wtsapi32 = windows.NewLazySystemDLL("wtsapi32.dll")

	procGetSystemMetrics           = user32.NewProc("GetSystemMetrics")
	procGetDC                      = user32.NewProc("GetDC")
	procReleaseDC                  = user32.NewProc("ReleaseDC")
	procSendInput                  = user32.NewProc("SendInput")
	procCreateCompatibleDC         = gdi32.NewProc("CreateCompatibleDC")
	procCreateCompatibleBitmap     = gdi32.NewProc("CreateCompatibleBitmap")
	procSelectObject               = gdi32.NewProc("SelectObject")
	procBitBlt                     = gdi32.NewProc("BitBlt")
	procGetDIBits                  = gdi32.NewProc("GetDIBits")
	procDeleteObject               = gdi32.NewProc("DeleteObject")
	procDeleteDC                   = gdi32.NewProc("DeleteDC")
	procProcessIdToSessionId       = kernel32.NewProc("ProcessIdToSessionId")
	procCreateNamedPipeW           = kernel32.NewProc("CreateNamedPipeW")
	procConnectNamedPipe           = kernel32.NewProc("ConnectNamedPipe")
	procReadFile                   = kernel32.NewProc("ReadFile")
	procWriteFile                  = kernel32.NewProc("WriteFile")
	procCreateFileW                = kernel32.NewProc("CreateFileW")
	procWTSGetActiveConsoleSession          = kernel32.NewProc("WTSGetActiveConsoleSessionId")
	procWTSQueryUserToken                   = wtsapi32.NewProc("WTSQueryUserToken")
	procCreateProcessAsUserW                = advapi32.NewProc("CreateProcessAsUserW")
	procInitializeSecurityDescriptor        = advapi32.NewProc("InitializeSecurityDescriptor")
	procSetSecurityDescriptorDacl           = advapi32.NewProc("SetSecurityDescriptorDacl")
)

// ─── GDI constants ────────────────────────────────────────────────────────────

const (
	smCXScreen   = 0
	smCYScreen   = 1
	srccopy      = 0x00CC0020
	biRGB        = 0
	dibRGBColors = 0
)

// ─── Screen capture (GDI) ─────────────────────────────────────────────────────

type bitmapInfoHeader struct {
	biSize          uint32
	biWidth         int32
	biHeight        int32
	biPlanes        uint16
	biBitCount      uint16
	biCompression   uint32
	biSizeImage     uint32
	biXPelsPerMeter int32
	biYPelsPerMeter int32
	biClrUsed       uint32
	biClrImportant  uint32
}

type bitmapInfo struct {
	bmiHeader bitmapInfoHeader
	bmiColors [1]uint32
}

// captureScreenJPEG captures the screen and returns raw JPEG bytes.
func captureScreenJPEG(quality int) ([]byte, int, int, error) {
	w, _, _ := procGetSystemMetrics.Call(smCXScreen)
	h, _, _ := procGetSystemMetrics.Call(smCYScreen)
	width, height := int(w), int(h)
	if width == 0 || height == 0 {
		return nil, 0, 0, fmt.Errorf("dimensões de tela inválidas")
	}

	screenDC, _, _ := procGetDC.Call(0)
	if screenDC == 0 {
		return nil, 0, 0, fmt.Errorf("GetDC falhou")
	}
	defer procReleaseDC.Call(0, screenDC)

	memDC, _, _ := procCreateCompatibleDC.Call(screenDC)
	if memDC == 0 {
		return nil, 0, 0, fmt.Errorf("CreateCompatibleDC falhou")
	}
	defer procDeleteDC.Call(memDC)

	bmp, _, _ := procCreateCompatibleBitmap.Call(screenDC, uintptr(width), uintptr(height))
	if bmp == 0 {
		return nil, 0, 0, fmt.Errorf("CreateCompatibleBitmap falhou")
	}
	defer procDeleteObject.Call(bmp)

	old, _, _ := procSelectObject.Call(memDC, bmp)
	defer procSelectObject.Call(memDC, old)

	ret, _, _ := procBitBlt.Call(memDC, 0, 0, uintptr(width), uintptr(height), screenDC, 0, 0, srccopy)
	if ret == 0 {
		return nil, 0, 0, fmt.Errorf("BitBlt falhou")
	}

	bmi := bitmapInfo{}
	bmi.bmiHeader.biSize = uint32(unsafe.Sizeof(bmi.bmiHeader))
	bmi.bmiHeader.biWidth = int32(width)
	bmi.bmiHeader.biHeight = -int32(height) // negative = top-down
	bmi.bmiHeader.biPlanes = 1
	bmi.bmiHeader.biBitCount = 32
	bmi.bmiHeader.biCompression = biRGB

	pixels := make([]byte, width*height*4)
	ret, _, _ = procGetDIBits.Call(
		memDC, bmp, 0, uintptr(height),
		uintptr(unsafe.Pointer(&pixels[0])),
		uintptr(unsafe.Pointer(&bmi)),
		dibRGBColors,
	)
	if ret == 0 {
		return nil, 0, 0, fmt.Errorf("GetDIBits falhou")
	}

	// GDI returns BGRA; image/jpeg needs RGBA
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for i := 0; i < width*height; i++ {
		img.Pix[i*4+0] = pixels[i*4+2]
		img.Pix[i*4+1] = pixels[i*4+1]
		img.Pix[i*4+2] = pixels[i*4+0]
		img.Pix[i*4+3] = 255
	}

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, &jpeg.Options{Quality: quality}); err != nil {
		return nil, 0, 0, err
	}
	return buf.Bytes(), width, height, nil
}

// ─── Session 0 detection ──────────────────────────────────────────────────────

func isSession0() bool {
	var sessionID uint32
	procProcessIdToSessionId.Call(uintptr(os.Getpid()), uintptr(unsafe.Pointer(&sessionID)))
	return sessionID == 0
}

// ─── captureLoop: routes to direct or subprocess based on session ─────────────

func captureLoop(ctx context.Context, fps, quality int, send FrameSender) {
	if fps <= 0 {
		fps = 10
	}
	if quality <= 0 || quality > 100 {
		quality = 60
	}
	if isSession0() {
		log.Println("remote: Session 0 detectada — usando processo auxiliar na sessão interativa")
		captureLoopViaSubprocess(ctx, fps, quality, send)
	} else {
		captureLoopDirect(ctx, fps, quality, send)
	}
}

func captureLoopDirect(ctx context.Context, fps, quality int, send FrameSender) {
	ticker := time.NewTicker(time.Second / time.Duration(fps))
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			data, w, h, err := captureScreenJPEG(quality)
			if err != nil {
				log.Printf("remote: captura falhou: %v", err)
				continue
			}
			send(base64.StdEncoding.EncodeToString(data), w, h)
		}
	}
}

// ─── Subprocess capture (Session 0 → spawn helper in interactive session) ─────

// Named pipe frame format: [jpegLen uint32 LE][width uint32 LE][height uint32 LE][JPEG bytes]

const (
	pipeAccessInbound = 0x00000001
	pipeTypeByte      = 0x00000000
	pipeWait          = 0x00000000
	fileGenericWrite  = 0x40000000
	fileOpenExisting  = 3
	fileAttrNormal    = 0x00000080
	invalidHandle     = ^uintptr(0)
	createNoWindow    = 0x08000000
)

func captureLoopViaSubprocess(ctx context.Context, fps, quality int, send FrameSender) {
	activeSession, _, _ := procWTSGetActiveConsoleSession.Call()
	if activeSession == 0xFFFFFFFF {
		log.Println("remote: sem sessão de console ativa, aguardando...")
		<-ctx.Done()
		return
	}

	var userToken windows.Token
	ret, _, err := procWTSQueryUserToken.Call(activeSession, uintptr(unsafe.Pointer(&userToken)))
	if ret == 0 {
		log.Printf("remote: WTSQueryUserToken falhou (%v), tentando captura direta", err)
		captureLoopDirect(ctx, fps, quality, send)
		return
	}
	defer userToken.Close()

	pipeName := fmt.Sprintf(`\\.\pipe\sollorm-screen-%d`, os.Getpid())
	pipeNameW, _ := windows.UTF16PtrFromString(pipeName)

	// NULL DACL so the interactive-session user can write to the pipe.
	// Default DACL created by SYSTEM only grants write to admins/SYSTEM.
	var sdBuf [256]byte // oversized buffer for SECURITY_DESCRIPTOR (40 bytes on 64-bit)
	procInitializeSecurityDescriptor.Call(uintptr(unsafe.Pointer(&sdBuf[0])), 1)
	procSetSecurityDescriptorDacl.Call(uintptr(unsafe.Pointer(&sdBuf[0])), 1, 0, 0) // bDaclPresent=TRUE, pDacl=NULL
	sa := windows.SecurityAttributes{
		Length:             uint32(unsafe.Sizeof(windows.SecurityAttributes{})),
		SecurityDescriptor: (*windows.SECURITY_DESCRIPTOR)(unsafe.Pointer(&sdBuf[0])),
	}

	hPipe, _, err := procCreateNamedPipeW.Call(
		uintptr(unsafe.Pointer(pipeNameW)),
		pipeAccessInbound, pipeTypeByte|pipeWait,
		1,      // max instances
		0,      // out buffer (read-only pipe, ignored)
		4<<20,  // in buffer 4MB
		0,      // default timeout
		uintptr(unsafe.Pointer(&sa)), // NULL DACL → everyone can connect
	)
	if hPipe == invalidHandle {
		log.Printf("remote: CreateNamedPipe falhou: %v", err)
		<-ctx.Done()
		return
	}

	// Close pipe handle on context cancel so blocked ReadFile/ConnectNamedPipe unblocks.
	var closeOnce sync.Once
	closePipe := func() { closeOnce.Do(func() { windows.CloseHandle(windows.Handle(hPipe)) }) }
	defer closePipe()

	go func() {
		<-ctx.Done()
		closePipe()
	}()

	// Launch helper in the user's interactive session
	exePath, _ := os.Executable()
	cmdLine := fmt.Sprintf(
		`"%s" --screen-helper "%s" --screen-helper-fps %d --screen-helper-quality %d`,
		exePath, pipeName, fps, quality,
	)
	cmdLineW, _ := windows.UTF16PtrFromString(cmdLine)
	desktopW, _ := windows.UTF16PtrFromString("winsta0\\Default")

	si := windows.StartupInfo{
		Cb:      uint32(unsafe.Sizeof(windows.StartupInfo{})),
		Desktop: desktopW,
	}
	var pi windows.ProcessInformation

	if err := windows.CreateProcessAsUser(
		userToken, nil, cmdLineW,
		nil, nil, false,
		createNoWindow,
		nil, nil, &si, &pi,
	); err != nil {
		log.Printf("remote: CreateProcessAsUser falhou: %v", err)
		<-ctx.Done()
		return
	}
	defer windows.CloseHandle(pi.Process)
	defer windows.CloseHandle(pi.Thread)
	log.Printf("remote: processo auxiliar iniciado (PID %d)", pi.ProcessId)

	// Wait for helper to connect (with timeout)
	connected := make(chan bool, 1)
	go func() {
		r, _, _ := procConnectNamedPipe.Call(hPipe, 0)
		connected <- r != 0
	}()

	select {
	case <-ctx.Done():
		return
	case ok := <-connected:
		if !ok {
			log.Println("remote: helper não conectou ao pipe")
			return
		}
	case <-time.After(15 * time.Second):
		log.Println("remote: timeout aguardando helper conectar")
		return
	}

	log.Println("remote: helper conectado, recebendo frames")

	// Read frames until context or pipe error
	header := make([]byte, 12)
	for {
		if !readFullPipe(hPipe, header) {
			return
		}
		jpegLen := binary.LittleEndian.Uint32(header[0:4])
		width   := int(binary.LittleEndian.Uint32(header[4:8]))
		height  := int(binary.LittleEndian.Uint32(header[8:12]))

		if jpegLen == 0 || jpegLen > 20<<20 {
			return
		}
		jpeg := make([]byte, jpegLen)
		if !readFullPipe(hPipe, jpeg) {
			return
		}
		send(base64.StdEncoding.EncodeToString(jpeg), width, height)
	}
}

func readFullPipe(hPipe uintptr, buf []byte) bool {
	total := 0
	for total < len(buf) {
		var n uint32
		ret, _, _ := procReadFile.Call(
			hPipe,
			uintptr(unsafe.Pointer(&buf[total])),
			uintptr(len(buf)-total),
			uintptr(unsafe.Pointer(&n)),
			0,
		)
		if ret == 0 || n == 0 {
			return false
		}
		total += int(n)
	}
	return true
}

// ─── RunScreenHelper: runs in the user session, sends frames via named pipe ───

// RunScreenHelper is called when the binary is invoked with --screen-helper.
// It runs in the interactive user session spawned by captureLoopViaSubprocess.
func RunScreenHelper(pipeName string, fps, quality int) {
	if fps <= 0 {
		fps = 10
	}
	if quality <= 0 || quality > 100 {
		quality = 65
	}

	// Connect to named pipe server (with retries)
	pipeNameW, _ := windows.UTF16PtrFromString(pipeName)
	var hPipe uintptr
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		h, _, _ := procCreateFileW.Call(
			uintptr(unsafe.Pointer(pipeNameW)),
			fileGenericWrite, 0, 0,
			fileOpenExisting, fileAttrNormal, 0,
		)
		if h != invalidHandle {
			hPipe = h
			break
		}
		time.Sleep(200 * time.Millisecond)
	}
	if hPipe == 0 {
		log.Println("screen-helper: falha ao conectar ao pipe")
		return
	}
	defer windows.CloseHandle(windows.Handle(hPipe))

	log.Printf("screen-helper: conectado ao pipe, capturando a %d fps quality=%d", fps, quality)

	interval := time.Second / time.Duration(fps)
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		data, w, h, err := captureScreenJPEG(quality)
		if err != nil {
			log.Printf("screen-helper: captura falhou: %v", err)
			continue
		}
		if !writeFramePipe(hPipe, data, w, h) {
			log.Println("screen-helper: pipe fechado pelo servidor, encerrando")
			return
		}
	}
}

func writeFramePipe(hPipe uintptr, data []byte, w, h int) bool {
	header := make([]byte, 12)
	binary.LittleEndian.PutUint32(header[0:4], uint32(len(data)))
	binary.LittleEndian.PutUint32(header[4:8], uint32(w))
	binary.LittleEndian.PutUint32(header[8:12], uint32(h))

	var n uint32
	if ret, _, _ := procWriteFile.Call(hPipe, uintptr(unsafe.Pointer(&header[0])), 12, uintptr(unsafe.Pointer(&n)), 0); ret == 0 {
		return false
	}
	if len(data) == 0 {
		return true
	}
	ret, _, _ := procWriteFile.Call(hPipe, uintptr(unsafe.Pointer(&data[0])), uintptr(len(data)), uintptr(unsafe.Pointer(&n)), 0)
	return ret != 0
}

// ─── Input injection ──────────────────────────────────────────────────────────

const sizeofInput = 40

const (
	inputMouse    uint32 = 0
	inputKeyboard uint32 = 1

	mousefMove        uint32 = 0x0001
	mousefLeftDown    uint32 = 0x0002
	mousefLeftUp      uint32 = 0x0004
	mousefRightDown   uint32 = 0x0008
	mousefRightUp     uint32 = 0x0010
	mousefMiddleDown  uint32 = 0x0020
	mousefMiddleUp    uint32 = 0x0040
	mousefAbsolute    uint32 = 0x8000
	mousefVirtualDesk uint32 = 0x4000

	keyEventfExtended uint32 = 0x0001
	keyEventfKeyUp    uint32 = 0x0002
)

func buildMouseBuf(dx, dy int32, flags uint32) []byte {
	buf := make([]byte, sizeofInput)
	binary.LittleEndian.PutUint32(buf[0:4], inputMouse)
	binary.LittleEndian.PutUint32(buf[8:12], uint32(dx))
	binary.LittleEndian.PutUint32(buf[12:16], uint32(dy))
	binary.LittleEndian.PutUint32(buf[20:24], flags)
	return buf
}

func buildKeyBuf(vk uint16, flags uint32) []byte {
	buf := make([]byte, sizeofInput)
	binary.LittleEndian.PutUint32(buf[0:4], inputKeyboard)
	binary.LittleEndian.PutUint16(buf[8:10], vk)
	binary.LittleEndian.PutUint16(buf[10:12], 0)
	binary.LittleEndian.PutUint32(buf[12:16], flags)
	return buf
}

func callSendInput(buf []byte) {
	procSendInput.Call(1, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
}

func injectMouse(x, y float64, event string, button int) {
	dx := int32(x * 65535)
	dy := int32(y * 65535)
	flags := mousefAbsolute | mousefVirtualDesk | mousefMove
	switch event {
	case "down":
		switch button {
		case 0:
			flags |= mousefLeftDown
		case 1:
			flags |= mousefRightDown
		case 2:
			flags |= mousefMiddleDown
		}
	case "up":
		switch button {
		case 0:
			flags |= mousefLeftUp
		case 1:
			flags |= mousefRightUp
		case 2:
			flags |= mousefMiddleUp
		}
	}
	callSendInput(buildMouseBuf(dx, dy, flags))
}

type vkEntry struct {
	vk       uint16
	extended bool
}

var jsCodeToVK = map[string]vkEntry{
	"KeyA": {0x41, false}, "KeyB": {0x42, false}, "KeyC": {0x43, false},
	"KeyD": {0x44, false}, "KeyE": {0x45, false}, "KeyF": {0x46, false},
	"KeyG": {0x47, false}, "KeyH": {0x48, false}, "KeyI": {0x49, false},
	"KeyJ": {0x4A, false}, "KeyK": {0x4B, false}, "KeyL": {0x4C, false},
	"KeyM": {0x4D, false}, "KeyN": {0x4E, false}, "KeyO": {0x4F, false},
	"KeyP": {0x50, false}, "KeyQ": {0x51, false}, "KeyR": {0x52, false},
	"KeyS": {0x53, false}, "KeyT": {0x54, false}, "KeyU": {0x55, false},
	"KeyV": {0x56, false}, "KeyW": {0x57, false}, "KeyX": {0x58, false},
	"KeyY": {0x59, false}, "KeyZ": {0x5A, false},
	"Digit0": {0x30, false}, "Digit1": {0x31, false}, "Digit2": {0x32, false},
	"Digit3": {0x33, false}, "Digit4": {0x34, false}, "Digit5": {0x35, false},
	"Digit6": {0x36, false}, "Digit7": {0x37, false}, "Digit8": {0x38, false},
	"Digit9": {0x39, false},
	"F1":  {0x70, false}, "F2": {0x71, false}, "F3": {0x72, false},
	"F4":  {0x73, false}, "F5": {0x74, false}, "F6": {0x75, false},
	"F7":  {0x76, false}, "F8": {0x77, false}, "F9": {0x78, false},
	"F10": {0x79, false}, "F11": {0x7A, false}, "F12": {0x7B, false},
	"ShiftLeft": {0x10, false}, "ShiftRight": {0x10, false},
	"ControlLeft": {0x11, false}, "ControlRight": {0x11, true},
	"AltLeft": {0x12, false}, "AltRight": {0x12, true},
	"MetaLeft": {0x5B, true}, "MetaRight": {0x5C, true},
	"Space":     {0x20, false},
	"Enter":     {0x0D, false},
	"Backspace": {0x08, false},
	"Tab":       {0x09, false},
	"Escape":    {0x1B, false},
	"CapsLock":  {0x14, false},
	"Delete":    {0x2E, true}, "Insert": {0x2D, true},
	"Home":      {0x24, true}, "End": {0x23, true},
	"PageUp":    {0x21, true}, "PageDown": {0x22, true},
	"ArrowLeft":  {0x25, true}, "ArrowUp": {0x26, true},
	"ArrowRight": {0x27, true}, "ArrowDown": {0x28, true},
	"Minus":        {0xBD, false}, "Equal": {0xBB, false},
	"BracketLeft":  {0xDB, false}, "BracketRight": {0xDD, false},
	"Backslash":    {0xDC, false}, "Semicolon": {0xBA, false},
	"Quote":        {0xDE, false}, "Comma": {0xBC, false},
	"Period":       {0xBE, false}, "Slash": {0xBF, false},
	"Backquote":    {0xC0, false},
	"Numpad0": {0x60, false}, "Numpad1": {0x61, false}, "Numpad2": {0x62, false},
	"Numpad3": {0x63, false}, "Numpad4": {0x64, false}, "Numpad5": {0x65, false},
	"Numpad6": {0x66, false}, "Numpad7": {0x67, false}, "Numpad8": {0x68, false},
	"Numpad9": {0x69, false},
	"NumpadDecimal":  {0x6E, false},
	"NumpadAdd":      {0x6B, false},
	"NumpadSubtract": {0x6D, false},
	"NumpadMultiply": {0x6A, false},
	"NumpadDivide":   {0x6F, true},
	"NumpadEnter":    {0x0D, true},
	"PrintScreen": {0x2C, false}, "ScrollLock": {0x91, false},
	"Pause":       {0x13, false}, "NumLock": {0x90, false},
	"ContextMenu": {0x5D, true},
}

func injectKey(code, event string) {
	entry, ok := jsCodeToVK[code]
	if !ok {
		return
	}
	flags := uint32(0)
	if entry.extended {
		flags |= keyEventfExtended
	}
	if event == "up" {
		flags |= keyEventfKeyUp
	}
	callSendInput(buildKeyBuf(entry.vk, flags))
}
