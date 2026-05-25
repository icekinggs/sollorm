//go:build linux

package commands

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

func SelfUpdate(downloadURL string) error {
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("não foi possível determinar executável: %w", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, "GET", downloadURL, nil)
	if err != nil {
		return err
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("falha no download: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("download retornou HTTP %d", resp.StatusCode)
	}

	tmpPath := exe + ".new"
	f, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return fmt.Errorf("não foi possível criar arquivo temporário: %w", err)
	}
	if _, err := io.Copy(f, resp.Body); err != nil {
		f.Close()
		os.Remove(tmpPath)
		return fmt.Errorf("erro ao escrever binário: %w", err)
	}
	f.Close()

	// Atomic replace — on Linux the running process holds the old inode
	if err := os.Rename(tmpPath, exe); err != nil {
		os.Remove(tmpPath)
		return fmt.Errorf("falha ao substituir binário: %w", err)
	}

	return nil
}
