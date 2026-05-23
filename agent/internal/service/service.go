// Package service implementa o loop principal do agente, compatível com
// rodar como processo normal ou como serviço de sistema (Windows Service / systemd).
package service

import (
	"context"
	"log"
	"time"

	ksvc "github.com/kardianos/service"

	"sollorm-agent/internal/reporter"
	"sollorm-agent/internal/system"
)

const (
	HeartbeatInterval  = 60 * time.Second
	SystemInfoInterval = 30 * time.Minute
)

// Program implementa ksvc.Interface
type Program struct {
	Reporter *reporter.Reporter
	cancel   context.CancelFunc
	done     chan struct{}
}

func New(rep *reporter.Reporter) *Program {
	return &Program{
		Reporter: rep,
		done:     make(chan struct{}),
	}
}

// Start é chamado pelo gerenciador de serviço quando o serviço inicia.
// IMPORTANTE: Start NÃO PODE bloquear - precisa retornar rápido.
func (p *Program) Start(s ksvc.Service) error {
	log.Printf("SolloRMM Agent v%s iniciando...", reporter.AgentVersion)
	ctx, cancel := context.WithCancel(context.Background())
	p.cancel = cancel
	go p.run(ctx)
	return nil
}

// Stop é chamado quando o serviço deve parar.
func (p *Program) Stop(s ksvc.Service) error {
	log.Println("SolloRMM Agent parando...")
	if p.cancel != nil {
		p.cancel()
	}
	// Espera o loop terminar (com timeout pra não travar shutdown)
	select {
	case <-p.done:
	case <-time.After(5 * time.Second):
		log.Println("Timeout esperando loop terminar")
	}
	return nil
}

func (p *Program) run(ctx context.Context) {
	defer close(p.done)
	log.Println(">>> run() iniciado")

	// Envio inicial de system info
	log.Println(">>> Coletando system info...")
	info, err := system.CollectInfo()
	if err != nil {
		log.Printf(">>> ERRO ao coletar system info: %v", err)
	} else {
		log.Printf(">>> System info coletado: %s (%s) - %d cores, %d MB RAM",
			info.Hostname, info.Platform, info.CPUCores, info.RAMTotal/1024/1024)
		log.Println(">>> Enviando system info pro backend...")
		if err := p.Reporter.SendSystemInfo(ctx, info); err != nil {
			log.Printf(">>> ERRO ao enviar system info: %v", err)
		} else {
			log.Println(">>> System info enviado COM SUCESSO!")
		}
	}

	// Primeiro heartbeat imediato
	log.Println(">>> Enviando primeiro heartbeat...")
	p.sendHeartbeat(ctx)

	heartbeatTicker := time.NewTicker(HeartbeatInterval)
	systemInfoTicker := time.NewTicker(SystemInfoInterval)
	defer heartbeatTicker.Stop()
	defer systemInfoTicker.Stop()

	for {
		select {
		case <-ctx.Done():
			log.Println(">>> Contexto cancelado, parando run()")
			return

		case <-heartbeatTicker.C:
			p.sendHeartbeat(ctx)

		case <-systemInfoTicker.C:
			log.Println(">>> Tick de system info...")
			if info, err := system.CollectInfo(); err == nil {
				if err := p.Reporter.SendSystemInfo(ctx, info); err != nil {
					log.Printf(">>> ERRO ao enviar system info: %v", err)
				}
			}
		}
	}
}

func (p *Program) sendHeartbeat(ctx context.Context) {
	m, err := system.CollectMetrics()
	if err != nil {
		log.Printf("Erro ao coletar métricas: %v", err)
		return
	}
	log.Printf("Heartbeat: CPU=%.1f%% RAM=%.1f%% DISK=%.1f%%", m.CPUUsage, m.RAMUsage, m.DiskUsage)
	if err := p.Reporter.SendHeartbeat(ctx, m); err != nil {
		log.Printf("Erro no heartbeat: %v", err)
	}
}
