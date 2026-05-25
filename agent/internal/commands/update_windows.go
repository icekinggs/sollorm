//go:build windows

package commands

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"
)

func SelfUpdate(downloadURL string) error {
	exe, err := os.Executable()
	if err != nil {
		return fmt.Errorf("não foi possível determinar executável: %w", err)
	}

	tmpPath := filepath.Join(os.TempDir(), "sollorm-agent-new.exe")

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

	// PS script runs after this process exits and restarts the service
	scriptPath := filepath.Join(os.TempDir(), "sollorm-update.ps1")
	script := fmt.Sprintf(
		"Start-Sleep 3\nStop-Service SolloRMMAgent -ErrorAction SilentlyContinue\n"+
			"Copy-Item -Force '%s' '%s'\nStart-Service SolloRMMAgent\n"+
			"Remove-Item '%s' -ErrorAction SilentlyContinue\n",
		tmpPath, exe, scriptPath,
	)
	if err := os.WriteFile(scriptPath, []byte(script), 0644); err != nil {
		return fmt.Errorf("não foi possível criar script de atualização: %w", err)
	}

	cmd := exec.Command("powershell.exe",
		"-NoProfile", "-ExecutionPolicy", "Bypass",
		"-WindowStyle", "Hidden", "-NonInteractive",
		"-File", scriptPath,
	)
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("não foi possível iniciar script de atualização: %w", err)
	}
	cmd.Process.Release()

	return nil
}
