//go:build !windows

package remote

import "context"

func captureLoop(_ context.Context, _, _ int, _ FrameSender) {}
func injectMouse(_, _ float64, _ string, _ int)               {}
func injectKey(_, _ string)                                   {}

// RunScreenHelper is a no-op on non-Windows platforms.
func RunScreenHelper(_ string, _, _ int) {}
