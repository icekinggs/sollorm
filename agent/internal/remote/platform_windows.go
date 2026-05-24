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
	"time"
	"unsafe"

	"golang.org/x/sys/windows"
)

// ─── DLL / proc handles ───────────────────────────────────────────────────────

var (
	user32 = windows.NewLazySystemDLL("user32.dll")
	gdi32  = windows.NewLazySystemDLL("gdi32.dll")

	procGetSystemMetrics       = user32.NewProc("GetSystemMetrics")
	procGetDC                  = user32.NewProc("GetDC")
	procReleaseDC              = user32.NewProc("ReleaseDC")
	procCreateCompatibleDC     = gdi32.NewProc("CreateCompatibleDC")
	procCreateCompatibleBitmap = gdi32.NewProc("CreateCompatibleBitmap")
	procSelectObject           = gdi32.NewProc("SelectObject")
	procBitBlt                 = gdi32.NewProc("BitBlt")
	procGetDIBits              = gdi32.NewProc("GetDIBits")
	procDeleteObject           = gdi32.NewProc("DeleteObject")
	procDeleteDC               = gdi32.NewProc("DeleteDC")
	procSendInput              = user32.NewProc("SendInput")
)

// ─── GDI constants ────────────────────────────────────────────────────────────

const (
	smCXScreen    = 0
	smCYScreen    = 1
	srccopy       = 0x00CC0020
	biRGB         = 0
	dibRGBColors  = 0
)

// ─── Screen capture ───────────────────────────────────────────────────────────

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

func captureScreen(quality int) (string, int, int, error) {
	w, _, _ := procGetSystemMetrics.Call(smCXScreen)
	h, _, _ := procGetSystemMetrics.Call(smCYScreen)
	width, height := int(w), int(h)
	if width == 0 || height == 0 {
		return "", 0, 0, fmt.Errorf("dimensões de tela inválidas")
	}

	screenDC, _, _ := procGetDC.Call(0)
	if screenDC == 0 {
		return "", 0, 0, fmt.Errorf("GetDC falhou")
	}
	defer procReleaseDC.Call(0, screenDC)

	memDC, _, _ := procCreateCompatibleDC.Call(screenDC)
	if memDC == 0 {
		return "", 0, 0, fmt.Errorf("CreateCompatibleDC falhou")
	}
	defer procDeleteDC.Call(memDC)

	bmp, _, _ := procCreateCompatibleBitmap.Call(screenDC, uintptr(width), uintptr(height))
	if bmp == 0 {
		return "", 0, 0, fmt.Errorf("CreateCompatibleBitmap falhou")
	}
	defer procDeleteObject.Call(bmp)

	old, _, _ := procSelectObject.Call(memDC, bmp)
	defer procSelectObject.Call(memDC, old)

	ret, _, _ := procBitBlt.Call(memDC, 0, 0, uintptr(width), uintptr(height), screenDC, 0, 0, srccopy)
	if ret == 0 {
		return "", 0, 0, fmt.Errorf("BitBlt falhou")
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
		return "", 0, 0, fmt.Errorf("GetDIBits falhou")
	}

	// GDI returns BGRA; image/jpeg needs RGBA.
	img := image.NewRGBA(image.Rect(0, 0, width, height))
	for i := 0; i < width*height; i++ {
		img.Pix[i*4+0] = pixels[i*4+2] // R
		img.Pix[i*4+1] = pixels[i*4+1] // G
		img.Pix[i*4+2] = pixels[i*4+0] // B
		img.Pix[i*4+3] = 255
	}

	var buf bytes.Buffer
	if err := jpeg.Encode(&buf, img, &jpeg.Options{Quality: quality}); err != nil {
		return "", 0, 0, err
	}

	return base64.StdEncoding.EncodeToString(buf.Bytes()), width, height, nil
}

func captureLoop(ctx context.Context, fps, quality int, send FrameSender) {
	if fps <= 0 {
		fps = 10
	}
	if quality <= 0 || quality > 100 {
		quality = 60
	}
	ticker := time.NewTicker(time.Second / time.Duration(fps))
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			data, w, h, err := captureScreen(quality)
			if err != nil {
				log.Printf("Captura de tela: %v", err)
				continue
			}
			send(data, w, h)
		}
	}
}

// ─── Input injection ──────────────────────────────────────────────────────────

// INPUT struct layout on 64-bit Windows is 40 bytes:
//   offset 0-3:  DWORD type
//   offset 4-7:  padding (alignment)
//   offset 8-39: union (MOUSEINPUT=32 bytes / KEYBDINPUT padded to 32 bytes)
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
	// [4:8] = padding, zeros
	// MOUSEINPUT starts at offset 8
	binary.LittleEndian.PutUint32(buf[8:12], uint32(dx))
	binary.LittleEndian.PutUint32(buf[12:16], uint32(dy))
	// mouseData [16:20] = 0
	binary.LittleEndian.PutUint32(buf[20:24], flags)
	// time [24:28] = 0, pad [28:32] = 0, extraInfo [32:40] = 0
	return buf
}

func buildKeyBuf(vk uint16, flags uint32) []byte {
	buf := make([]byte, sizeofInput)
	binary.LittleEndian.PutUint32(buf[0:4], inputKeyboard)
	// [4:8] = padding, zeros
	// KEYBDINPUT starts at offset 8
	binary.LittleEndian.PutUint16(buf[8:10], vk)   // wVk
	binary.LittleEndian.PutUint16(buf[10:12], 0)    // wScan
	binary.LittleEndian.PutUint32(buf[12:16], flags) // dwFlags
	// time [16:20] = 0, pad [20:24] = 0, extraInfo [24:32] = 0
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
	// Letters
	"KeyA": {0x41, false}, "KeyB": {0x42, false}, "KeyC": {0x43, false},
	"KeyD": {0x44, false}, "KeyE": {0x45, false}, "KeyF": {0x46, false},
	"KeyG": {0x47, false}, "KeyH": {0x48, false}, "KeyI": {0x49, false},
	"KeyJ": {0x4A, false}, "KeyK": {0x4B, false}, "KeyL": {0x4C, false},
	"KeyM": {0x4D, false}, "KeyN": {0x4E, false}, "KeyO": {0x4F, false},
	"KeyP": {0x50, false}, "KeyQ": {0x51, false}, "KeyR": {0x52, false},
	"KeyS": {0x53, false}, "KeyT": {0x54, false}, "KeyU": {0x55, false},
	"KeyV": {0x56, false}, "KeyW": {0x57, false}, "KeyX": {0x58, false},
	"KeyY": {0x59, false}, "KeyZ": {0x5A, false},
	// Digits
	"Digit0": {0x30, false}, "Digit1": {0x31, false}, "Digit2": {0x32, false},
	"Digit3": {0x33, false}, "Digit4": {0x34, false}, "Digit5": {0x35, false},
	"Digit6": {0x36, false}, "Digit7": {0x37, false}, "Digit8": {0x38, false},
	"Digit9": {0x39, false},
	// Function keys
	"F1":  {0x70, false}, "F2": {0x71, false}, "F3": {0x72, false},
	"F4":  {0x73, false}, "F5": {0x74, false}, "F6": {0x75, false},
	"F7":  {0x76, false}, "F8": {0x77, false}, "F9": {0x78, false},
	"F10": {0x79, false}, "F11": {0x7A, false}, "F12": {0x7B, false},
	// Modifiers
	"ShiftLeft":    {0x10, false},
	"ShiftRight":   {0x10, false},
	"ControlLeft":  {0x11, false},
	"ControlRight": {0x11, true},
	"AltLeft":      {0x12, false},
	"AltRight":     {0x12, true},
	"MetaLeft":     {0x5B, true},
	"MetaRight":    {0x5C, true},
	// Editing / navigation
	"Space":     {0x20, false},
	"Enter":     {0x0D, false},
	"Backspace": {0x08, false},
	"Tab":       {0x09, false},
	"Escape":    {0x1B, false},
	"CapsLock":  {0x14, false},
	"Delete":    {0x2E, true},
	"Insert":    {0x2D, true},
	"Home":      {0x24, true},
	"End":       {0x23, true},
	"PageUp":    {0x21, true},
	"PageDown":  {0x22, true},
	"ArrowLeft":  {0x25, true},
	"ArrowUp":    {0x26, true},
	"ArrowRight": {0x27, true},
	"ArrowDown":  {0x28, true},
	// Punctuation
	"Minus":        {0xBD, false},
	"Equal":        {0xBB, false},
	"BracketLeft":  {0xDB, false},
	"BracketRight": {0xDD, false},
	"Backslash":    {0xDC, false},
	"Semicolon":    {0xBA, false},
	"Quote":        {0xDE, false},
	"Comma":        {0xBC, false},
	"Period":       {0xBE, false},
	"Slash":        {0xBF, false},
	"Backquote":    {0xC0, false},
	// Numpad
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
	// System
	"PrintScreen": {0x2C, false},
	"ScrollLock":  {0x91, false},
	"Pause":       {0x13, false},
	"NumLock":     {0x90, false},
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
