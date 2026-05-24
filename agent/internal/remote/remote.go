package remote

import (
	"context"
	"sync"
)

// FrameSender is called with each captured JPEG frame (base64-encoded) and screen dimensions.
type FrameSender func(data string, width, height int)

// Session manages an active screen-capture session for one agent connection.
type Session struct {
	mu     sync.Mutex
	cancel context.CancelFunc
	active bool
}

func (s *Session) Start(fps, quality int, send FrameSender) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.active {
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	s.cancel = cancel
	s.active = true
	go func() {
		defer func() {
			s.mu.Lock()
			s.active = false
			s.mu.Unlock()
		}()
		captureLoop(ctx, fps, quality, send)
	}()
}

func (s *Session) Stop() {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.cancel != nil {
		s.cancel()
		s.cancel = nil
	}
	s.active = false
}

// InjectMouse injects a mouse event. x, y are normalized 0-1 screen coordinates.
// event is "move", "down", or "up"; button: 0=left, 1=right, 2=middle.
func (s *Session) InjectMouse(x, y float64, event string, button int) {
	injectMouse(x, y, event, button)
}

// InjectKey injects a keyboard event. code is a JS KeyboardEvent.code string.
// event is "down" or "up".
func (s *Session) InjectKey(code, event string) {
	injectKey(code, event)
}
