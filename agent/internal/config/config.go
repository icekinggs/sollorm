// Package config gerencia carregamento e validação da configuração do agente.
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
)

type Config struct {
	// Server é a URL base do backend SolloRMM (ex: https://rmm.sollobrasil.com.br)
	Server string `json:"server"`

	// Token é o token individual deste agente (sollo_xxx)
	Token string `json:"token"`

	// AgentID é o UUID persistente deste agente. Se vazio, será gerado e salvo.
	AgentID string `json:"agent_id,omitempty"`
}

// Load lê um arquivo JSON de configuração. Retorna erro se o arquivo não existir
// ou os campos obrigatórios estiverem vazios.
func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("ler config: %w", err)
	}

	var cfg Config
	if err := json.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parsear config: %w", err)
	}

	cfg.Server = strings.TrimSpace(cfg.Server)
	cfg.Token = strings.TrimSpace(cfg.Token)
	cfg.Server = strings.TrimRight(cfg.Server, "/")

	if cfg.Server == "" {
		return nil, fmt.Errorf("campo 'server' vazio no config")
	}
	if cfg.Token == "" {
		return nil, fmt.Errorf("campo 'token' vazio no config")
	}

	return &cfg, nil
}

// Save grava o config de volta no disco (usado para persistir o AgentID gerado).
func Save(path string, cfg *Config) error {
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	// Permissões restritivas: o config contém token
	return os.WriteFile(path, data, 0600)
}
