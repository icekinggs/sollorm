//go:build !linux && !windows

package patches

import (
	"fmt"
	"runtime"
)

func Scan() ([]PatchInfo, error) {
	return nil, fmt.Errorf("patch scan não suportado em %s", runtime.GOOS)
}

func Install(packages []string) (string, error) {
	return "", fmt.Errorf("patch install não suportado em %s", runtime.GOOS)
}
