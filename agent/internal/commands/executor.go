// Package commands handles remote script execution requested by the backend.
package commands

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os/exec"
	"runtime"
	"time"
)

type ScriptCommand struct {
	Type           string `json:"type"`
	ExecutionID    string `json:"execution_id"`
	Language       string `json:"language"`
	Script         string `json:"script"`
	TimeoutSeconds int    `json:"timeout_seconds"`
}

type ScriptResult struct {
	Type         string `json:"type"`
	ExecutionID  string `json:"execution_id"`
	Status       string `json:"status"`
	Stdout       string `json:"stdout"`
	Stderr       string `json:"stderr"`
	ExitCode     *int   `json:"exit_code"`
	ErrorMessage string `json:"error_message,omitempty"`
}

func Execute(ctx context.Context, command ScriptCommand) ScriptResult {
	timeout := time.Duration(command.TimeoutSeconds) * time.Second
	if timeout <= 0 {
		timeout = 60 * time.Second
	}

	runCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd, err := buildCommand(runCtx, command.Language, command.Script)
	if err != nil {
		return ScriptResult{
			Type:         "script_result",
			ExecutionID:  command.ExecutionID,
			Status:       "failed",
			ErrorMessage: err.Error(),
		}
	}

	var stdout bytes.Buffer
	var stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err = cmd.Run()
	result := ScriptResult{
		Type:        "script_result",
		ExecutionID: command.ExecutionID,
		Stdout:      stdout.String(),
		Stderr:      stderr.String(),
	}

	if errors.Is(runCtx.Err(), context.DeadlineExceeded) {
		result.Status = "timed_out"
		result.ErrorMessage = "tempo limite excedido"
		return result
	}

	if err != nil {
		result.Status = "failed"
		result.ErrorMessage = err.Error()
		if exitErr, ok := err.(*exec.ExitError); ok {
			code := exitErr.ExitCode()
			result.ExitCode = &code
		}
		return result
	}

	code := 0
	result.ExitCode = &code
	result.Status = "succeeded"
	return result
}

func buildCommand(ctx context.Context, language string, script string) (*exec.Cmd, error) {
	switch language {
	case "bash":
		if runtime.GOOS == "windows" {
			return nil, fmt.Errorf("bash não está disponível por padrão no Windows")
		}
		return exec.CommandContext(ctx, "bash", "-c", script), nil
	case "powershell":
		if runtime.GOOS == "windows" {
			return exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script), nil
		}
		return exec.CommandContext(ctx, "pwsh", "-NoProfile", "-Command", script), nil
	case "python":
		if runtime.GOOS == "windows" {
			return exec.CommandContext(ctx, "python", "-c", script), nil
		}
		return exec.CommandContext(ctx, "python3", "-c", script), nil
	default:
		return nil, fmt.Errorf("linguagem não suportada: %s", language)
	}
}
