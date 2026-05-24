// Package reporter envia dados coletados pro backend via HTTP.
package reporter

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"sollorm-agent/internal/software"
	"sollorm-agent/internal/system"
)

const (
	AgentVersion = "0.5.4"
	httpTimeout  = 30 * time.Second
)

type Reporter struct {
	serverURL string
	token     string
	agentID   string
	client    *http.Client
}

func New(serverURL, token, agentID string) *Reporter {
	return &Reporter{
		serverURL: serverURL,
		token:     token,
		agentID:   agentID,
		client:    &http.Client{Timeout: httpTimeout},
	}
}

func (r *Reporter) ServerURL() string {
	return r.serverURL
}

func (r *Reporter) Token() string {
	return r.token
}

func (r *Reporter) AgentID() string {
	return r.agentID
}

type systemInfoPayload struct {
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

type heartbeatPayload struct {
	AgentID   string    `json:"agent_id"`
	Hostname  string    `json:"hostname"`
	CPUUsage  float64   `json:"cpu_usage_percent"`
	RAMUsage  float64   `json:"ram_usage_percent"`
	DiskUsage float64   `json:"disk_usage_percent"`
	Uptime    uint64    `json:"uptime_seconds"`
	Timestamp time.Time `json:"timestamp"`
}

func (r *Reporter) SendSystemInfo(ctx context.Context, info *system.SystemInfo) error {
	payload := systemInfoPayload{
		AgentID:      r.agentID,
		Hostname:     info.Hostname,
		OS:           info.OS,
		Platform:     info.Platform,
		Architecture: info.Architecture,
		KernelArch:   info.KernelArch,
		Uptime:       info.Uptime,
		CPUModel:     info.CPUModel,
		CPUCores:     info.CPUCores,
		RAMTotal:     info.RAMTotal,
		DiskTotal:    info.DiskTotal,
		AgentVersion: AgentVersion,
		Timestamp:    time.Now().UTC(),
	}
	return r.post(ctx, "/api/v1/agents/system-info", payload)
}

func (r *Reporter) SendHeartbeat(ctx context.Context, m *system.SystemMetrics) error {
	payload := heartbeatPayload{
		AgentID:   r.agentID,
		Hostname:  m.Hostname,
		CPUUsage:  m.CPUUsage,
		RAMUsage:  m.RAMUsage,
		DiskUsage: m.DiskUsage,
		Uptime:    m.Uptime,
		Timestamp: time.Now().UTC(),
	}
	return r.post(ctx, "/api/v1/agents/heartbeat", payload)
}

type softwareSyncPayload struct {
	AgentID string          `json:"agent_id"`
	Items   []software.Item `json:"items"`
}

func (r *Reporter) SendSoftwareInventory(ctx context.Context, items []software.Item) error {
	payload := softwareSyncPayload{
		AgentID: r.agentID,
		Items:   items,
	}
	return r.post(ctx, fmt.Sprintf("/api/v1/agents/%s/software/sync", r.agentID), payload)
}

func (r *Reporter) post(ctx context.Context, path string, payload interface{}) error {
	body, err := json.Marshal(payload)
	if err != nil {
		return err
	}

	url := r.serverURL + path
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+r.token)
	req.Header.Set("User-Agent", "SolloRMM-Agent/"+AgentVersion)

	resp, err := r.client.Do(req)
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
