package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"runtime"
	"time"

	"github.com/google/uuid"
	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
)

const (
	agentVersion       = "0.2.0"
	heartbeatInterval  = 60 * time.Second
	systemInfoInterval = 30 * time.Minute
)

type SystemInfo struct {
	AgentID      string    `json:"agent_id"`
	Hostname     string    `json:"hostname"`
	OS           string    `json:"os"`
	Platform     string    `json:"platform"`
	Architecture string    `json:"architecture"`
	KernelArch   string    `json:"kernel_arch"`
	Uptime       uint64    `json:"uptime_seconds"`
	CPUModel     string    `json:"cpu_model"`
	CPUCores     int       `json:"cpu_cores"`
	RAMTotal     uint64    `json:"ram_total_bytes"`
	DiskTotal    uint64    `json:"disk_total_bytes"`
	AgentVersion string    `json:"agent_version"`
	Timestamp    time.Time `json:"timestamp"`
}

type Heartbeat struct {
	AgentID   string    `json:"agent_id"`
	Hostname  string    `json:"hostname"`
	CPUUsage  float64   `json:"cpu_usage_percent"`
	RAMUsage  float64   `json:"ram_usage_percent"`
	DiskUsage float64   `json:"disk_usage_percent"`
	Uptime    uint64    `json:"uptime_seconds"`
	Timestamp time.Time `json:"timestamp"`
}

type Config struct {
	ServerURL string
	Token     string
	AgentID   string
}

func main() {
	serverURL := flag.String("server", "", "URL do servidor SolloRMM (ex: https://api.sollobrasil.com.br)")
	token := flag.String("token", "", "Token de autenticação do agente")
	flag.Parse()

	if *serverURL == "" || *token == "" {
		log.Fatal("Parâmetros --server e --token são obrigatórios")
	}

	cfg := &Config{
		ServerURL: *serverURL,
		Token:     *token,
		AgentID:   getOrCreateAgentID(),
	}

	log.Printf("SolloRMM Agent v%s iniciando...", agentVersion)
	log.Printf("Agent ID: %s", cfg.AgentID)
	log.Printf("Servidor: %s", cfg.ServerURL)

	if err := sendSystemInfo(cfg); err != nil {
		log.Printf("Erro ao enviar system info inicial: %v", err)
	}

	heartbeatTicker := time.NewTicker(heartbeatInterval)
	systemInfoTicker := time.NewTicker(systemInfoInterval)
	defer heartbeatTicker.Stop()
	defer systemInfoTicker.Stop()

	if err := sendHeartbeat(cfg); err != nil {
		log.Printf("Erro no heartbeat inicial: %v", err)
	}

	for {
		select {
		case <-heartbeatTicker.C:
			if err := sendHeartbeat(cfg); err != nil {
				log.Printf("Erro no heartbeat: %v", err)
			}
		case <-systemInfoTicker.C:
			if err := sendSystemInfo(cfg); err != nil {
				log.Printf("Erro ao enviar system info: %v", err)
			}
		}
	}
}

func getOrCreateAgentID() string {
	idFile := "agent_id.txt"

	if data, err := os.ReadFile(idFile); err == nil {
		id := string(bytes.TrimSpace(data))
		if id != "" {
			return id
		}
	}

	newID := uuid.New().String()
	if err := os.WriteFile(idFile, []byte(newID), 0600); err != nil {
		log.Printf("Aviso: não foi possível salvar agent_id: %v", err)
	}
	return newID
}

func collectSystemInfo(cfg *Config) (*SystemInfo, error) {
	hostInfo, err := host.Info()
	if err != nil {
		return nil, fmt.Errorf("erro ao coletar host info: %w", err)
	}

	cpuInfo, err := cpu.Info()
	if err != nil {
		return nil, fmt.Errorf("erro ao coletar cpu info: %w", err)
	}

	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, fmt.Errorf("erro ao coletar mem info: %w", err)
	}

	diskInfo, err := disk.Usage("/")
	if err != nil {
		if runtime.GOOS == "windows" {
			diskInfo, err = disk.Usage("C:\\")
		}
		if err != nil {
			return nil, fmt.Errorf("erro ao coletar disk info: %w", err)
		}
	}

	cpuModel := "unknown"
	// runtime.NumCPU() é a fonte mais confiável: retorna o total de CPUs lógicas
	// que o SO enxerga (16 num Ryzen 7 5700X3D com SMT, por exemplo)
	cpuCores := runtime.NumCPU()
	if len(cpuInfo) > 0 {
		cpuModel = cpuInfo[0].ModelName
		// Em servidores multi-socket, gopsutil reporta cores físicos por socket.
		// Se isso for maior que NumCPU, usa esse valor.
		totalFromGopsutil := 0
		for _, c := range cpuInfo {
			totalFromGopsutil += int(c.Cores)
		}
		if totalFromGopsutil > cpuCores {
			cpuCores = totalFromGopsutil
		}
	}

	return &SystemInfo{
		AgentID:      cfg.AgentID,
		Hostname:     hostInfo.Hostname,
		OS:           hostInfo.OS,
		Platform:     hostInfo.Platform + " " + hostInfo.PlatformVersion,
		Architecture: runtime.GOARCH,
		KernelArch:   hostInfo.KernelArch,
		Uptime:       hostInfo.Uptime,
		CPUModel:     cpuModel,
		CPUCores:     cpuCores,
		RAMTotal:     memInfo.Total,
		DiskTotal:    diskInfo.Total,
		AgentVersion: agentVersion,
		Timestamp:    time.Now().UTC(),
	}, nil
}

func collectHeartbeat(cfg *Config) (*Heartbeat, error) {
	hostInfo, err := host.Info()
	if err != nil {
		return nil, err
	}

	cpuPercent, err := cpu.Percent(1*time.Second, false)
	if err != nil {
		return nil, err
	}
	cpuUsage := 0.0
	if len(cpuPercent) > 0 {
		cpuUsage = cpuPercent[0]
	}

	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, err
	}

	diskPath := "/"
	if runtime.GOOS == "windows" {
		diskPath = "C:\\"
	}
	diskInfo, err := disk.Usage(diskPath)
	if err != nil {
		return nil, err
	}

	return &Heartbeat{
		AgentID:   cfg.AgentID,
		Hostname:  hostInfo.Hostname,
		CPUUsage:  cpuUsage,
		RAMUsage:  memInfo.UsedPercent,
		DiskUsage: diskInfo.UsedPercent,
		Uptime:    hostInfo.Uptime,
		Timestamp: time.Now().UTC(),
	}, nil
}

func sendSystemInfo(cfg *Config) error {
	info, err := collectSystemInfo(cfg)
	if err != nil {
		return err
	}
	log.Printf("Enviando system info: %s (%s) - %d cores", info.Hostname, info.Platform, info.CPUCores)
	return postJSON(cfg, "/api/v1/agents/system-info", info)
}

func sendHeartbeat(cfg *Config) error {
	hb, err := collectHeartbeat(cfg)
	if err != nil {
		return err
	}
	log.Printf("Heartbeat: CPU=%.1f%% RAM=%.1f%% DISK=%.1f%%",
		hb.CPUUsage, hb.RAMUsage, hb.DiskUsage)
	return postJSON(cfg, "/api/v1/agents/heartbeat", hb)
}

func postJSON(cfg *Config, path string, payload interface{}) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	url := cfg.ServerURL + path
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
	if err != nil {
		return err
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+cfg.Token)
	req.Header.Set("User-Agent", "SolloRMM-Agent/"+agentVersion)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		respBody, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("status %d: %s", resp.StatusCode, string(respBody))
	}

	return nil
}
