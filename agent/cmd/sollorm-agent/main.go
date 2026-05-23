package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"runtime"
	"time"

	"github.com/google/uuid"
	ksvc "github.com/kardianos/service"

	"sollorm-agent/internal/config"
	"sollorm-agent/internal/reporter"
	"sollorm-agent/internal/service"
)

const (
	serviceName        = "SolloRMMAgent"
	serviceDisplayName = "SolloRMM Agent"
	serviceDescription = "SolloRMM monitoring agent"
)

func main() {
	configPath := flag.String("config", "", "Caminho para o arquivo config.json (usado quando --service)")
	serverFlag := flag.String("server", "", "URL do servidor (modo foreground sem config)")
	tokenFlag := flag.String("token", "", "Token de autenticação (modo foreground sem config)")
	serviceMode := flag.Bool("service", false, "Rodar como serviço do sistema (Windows Service / systemd)")
	installCmd := flag.Bool("install", false, "Instalar como serviço")
	uninstallCmd := flag.Bool("uninstall", false, "Desinstalar serviço")
	startCmd := flag.Bool("start", false, "Iniciar serviço")
	stopCmd := flag.Bool("stop", false, "Parar serviço")
	versionFlag := flag.Bool("version", false, "Mostrar versão e sair")
	flag.Parse()

	// Setup de logging: se rodando como serviço, escreve em arquivo;
	// senão (foreground/dev), continua no stderr padrão.
	if *serviceMode {
		logPath := ""
		if *configPath != "" {
			// agent.log fica ao lado do config.json
			logPath = filepath.Join(filepath.Dir(*configPath), "agent.log")
		} else {
			// fallback: ao lado do executável
			if exe, err := os.Executable(); err == nil {
				logPath = filepath.Join(filepath.Dir(exe), "agent.log")
			}
		}

		if logPath != "" {
			logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0640)
			if err == nil {
				log.SetOutput(logFile)
				log.SetFlags(log.LstdFlags | log.Lmicroseconds)
				log.Printf("=== SolloRMM Agent log iniciado em %s ===", time.Now().Format(time.RFC3339))
			}
		}
	}

	if *versionFlag {
		fmt.Printf("sollorm-agent v%s (%s/%s)\n", reporter.AgentVersion, runtime.GOOS, runtime.GOARCH)
		return
	}

	// Carrega config (de arquivo ou de flags)
	cfg, err := loadConfig(*configPath, *serverFlag, *tokenFlag)
	if err != nil {
		log.Fatalf("Configuração inválida: %v", err)
	}

	// Garante agent_id (persistido no config)
	if cfg.AgentID == "" {
		cfg.AgentID = uuid.New().String()
		if *configPath != "" {
			if err := config.Save(*configPath, cfg); err != nil {
				log.Printf("Aviso: não foi possível persistir agent_id: %v", err)
			}
		}
	}

	// Cria reporter e programa
	rep := reporter.New(cfg.Server, cfg.Token, cfg.AgentID)
	prog := service.New(rep)

	// Configuração do serviço
	svcConfig := &ksvc.Config{
		Name:        serviceName,
		DisplayName: serviceDisplayName,
		Description: serviceDescription,
	}
	if *configPath != "" {
		svcConfig.Arguments = []string{"--config", *configPath, "--service"}
	}

	s, err := ksvc.New(prog, svcConfig)
	if err != nil {
		log.Fatalf("Erro ao criar serviço: %v", err)
	}

	// Sub-comandos de gerenciamento (install/uninstall/start/stop)
	switch {
	case *installCmd:
		if err := s.Install(); err != nil {
			log.Fatalf("Erro ao instalar serviço: %v", err)
		}
		log.Println("Serviço instalado.")
		return
	case *uninstallCmd:
		if err := s.Uninstall(); err != nil {
			log.Fatalf("Erro ao desinstalar serviço: %v", err)
		}
		log.Println("Serviço desinstalado.")
		return
	case *startCmd:
		if err := s.Start(); err != nil {
			log.Fatalf("Erro ao iniciar serviço: %v", err)
		}
		log.Println("Serviço iniciado.")
		return
	case *stopCmd:
		if err := s.Stop(); err != nil {
			log.Fatalf("Erro ao parar serviço: %v", err)
		}
		log.Println("Serviço parado.")
		return
	}

	// Modo serviço: framework controla o ciclo de vida
	if *serviceMode {
		if err := s.Run(); err != nil {
			log.Fatalf("Erro ao rodar serviço: %v", err)
		}
		return
	}

	// Modo foreground (dev/teste): roda diretamente
	log.Printf("Rodando em modo foreground (dev). Use --service para rodar como serviço.")
	log.Printf("Agent ID: %s", cfg.AgentID)
	log.Printf("Servidor: %s", cfg.Server)
	if err := s.Run(); err != nil {
		log.Fatalf("Erro: %v", err)
	}
}

func loadConfig(configPath, serverFlag, tokenFlag string) (*config.Config, error) {
	// Caso 1: --config passado
	if configPath != "" {
		return config.Load(configPath)
	}

	// Caso 2: --server e --token passados (modo dev clássico)
	if serverFlag != "" && tokenFlag != "" {
		return &config.Config{
			Server: serverFlag,
			Token:  tokenFlag,
		}, nil
	}

	// Caso 3: procura config padrão no diretório do binário
	exe, err := os.Executable()
	if err == nil {
		defaultConfig := filepath.Join(filepath.Dir(exe), "config.json")
		if _, err := os.Stat(defaultConfig); err == nil {
			return config.Load(defaultConfig)
		}
	}

	return nil, fmt.Errorf("forneça --config ou --server e --token")
}
