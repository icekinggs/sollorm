//go:build !linux && !windows

package commands

import "fmt"

func SelfUpdate(_ string) error {
	return fmt.Errorf("auto-atualização não suportada nesta plataforma")
}
