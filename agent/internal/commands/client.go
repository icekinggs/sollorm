package commands

import (
	"context"
	"encoding/json"
	"log"
	"net/url"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/websocket"

	"sollorm-agent/internal/patches"
	"sollorm-agent/internal/remote"
)

const reconnectDelay = 10 * time.Second

type Client struct {
	serverURL     string
	token         string
	agentID       string
	remoteSession remote.Session
}

func NewClient(serverURL, token, agentID string) *Client {
	return &Client{
		serverURL: strings.TrimRight(serverURL, "/"),
		token:     token,
		agentID:   agentID,
	}
}

func (c *Client) Run(ctx context.Context) {
	for {
		if err := c.connectAndServe(ctx); err != nil {
			log.Printf("Canal de comandos desconectado: %v", err)
		}
		select {
		case <-ctx.Done():
			return
		case <-time.After(reconnectDelay):
		}
	}
}

func (c *Client) connectAndServe(ctx context.Context) error {
	wsURL, err := c.websocketURL()
	if err != nil {
		return err
	}

	conn, _, err := websocket.DefaultDialer.DialContext(ctx, wsURL, nil)
	if err != nil {
		return err
	}
	defer conn.Close()

	log.Println("Canal de comandos conectado")
	var writeMu sync.Mutex

	safeSend := func(v any) error {
		writeMu.Lock()
		defer writeMu.Unlock()
		return conn.WriteJSON(v)
	}

	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			return err
		}

		// Decodifica só o tipo para rotear
		var base struct {
			Type string `json:"type"`
		}
		if err := json.Unmarshal(data, &base); err != nil {
			log.Printf("Mensagem inválida recebida: %v", err)
			continue
		}

		switch base.Type {

		case "run_script":
			var command ScriptCommand
			if err := json.Unmarshal(data, &command); err != nil {
				log.Printf("Comando run_script inválido: %v", err)
				continue
			}
			if err := safeSend(map[string]string{
				"type":         "script_started",
				"execution_id": command.ExecutionID,
			}); err != nil {
				return err
			}
			go func(cmd ScriptCommand) {
				result := Execute(ctx, cmd)
				if err := safeSend(result); err != nil {
					log.Printf("Erro ao enviar resultado de script: %v", err)
				}
			}(command)

		case "scan_patches":
			var cmd struct {
				ScanID string `json:"scan_id"`
			}
			json.Unmarshal(data, &cmd)
			go c.handlePatchScan(ctx, cmd.ScanID, safeSend)

		case "install_patches":
			var cmd struct {
				ScanID   string   `json:"scan_id"`
				Packages []string `json:"packages"`
			}
			json.Unmarshal(data, &cmd)
			go c.handlePatchInstall(ctx, cmd.ScanID, cmd.Packages, safeSend)

		case "start_remote":
			var cmd struct {
				FPS     int `json:"fps"`
				Quality int `json:"quality"`
			}
			json.Unmarshal(data, &cmd)
			c.remoteSession.Start(cmd.FPS, cmd.Quality, func(data string, w, h int) {
				if err := safeSend(map[string]any{
					"type":   "remote_frame",
					"data":   data,
					"width":  w,
					"height": h,
				}); err != nil {
					log.Printf("Erro ao enviar frame remoto: %v", err)
				}
			})

		case "stop_remote":
			c.remoteSession.Stop()

		case "remote_mouse":
			var cmd struct {
				X      float64 `json:"x"`
				Y      float64 `json:"y"`
				Event  string  `json:"event"`
				Button int     `json:"button"`
			}
			json.Unmarshal(data, &cmd)
			c.remoteSession.InjectMouse(cmd.X, cmd.Y, cmd.Event, cmd.Button)

		case "remote_key":
			var cmd struct {
				Code  string `json:"code"`
				Event string `json:"event"`
			}
			json.Unmarshal(data, &cmd)
			c.remoteSession.InjectKey(cmd.Code, cmd.Event)

		default:
			log.Printf("Tipo de comando desconhecido: %q", base.Type)
		}
	}
}

// handlePatchScan executa o scan e reporta o resultado ao backend.
func (c *Client) handlePatchScan(ctx context.Context, scanID string, send func(any) error) {
	log.Printf("Iniciando scan de patches (scan_id=%s)", scanID)

	result := map[string]any{
		"type":     "patch_scan_result",
		"scan_id":  scanID,
		"agent_id": c.agentID,
	}

	list, err := patches.Scan()
	if err != nil {
		log.Printf("Erro no scan de patches: %v", err)
		result["error"] = err.Error()
		result["patches"] = []any{}
	} else {
		log.Printf("Scan de patches concluído: %d pacotes disponíveis", len(list))
		result["patches"] = list
	}

	if err := send(result); err != nil {
		log.Printf("Erro ao enviar resultado de patch scan: %v", err)
	}
}

// handlePatchInstall instala os pacotes e reporta ao backend.
func (c *Client) handlePatchInstall(ctx context.Context, scanID string, pkgs []string, send func(any) error) {
	log.Printf("Instalando %d pacote(s)...", len(pkgs))

	output, err := patches.Install(pkgs)

	result := map[string]any{
		"type":     "patch_install_result",
		"scan_id":  scanID,
		"agent_id": c.agentID,
		"output":   output,
	}
	if err != nil {
		result["error"] = err.Error()
		result["success"] = false
	} else {
		result["success"] = true
		result["installed"] = pkgs
	}

	if err := send(result); err != nil {
		log.Printf("Erro ao enviar resultado de patch install: %v", err)
	}
}

func (c *Client) websocketURL() (string, error) {
	parsed, err := url.Parse(c.serverURL)
	if err != nil {
		return "", err
	}
	if parsed.Scheme == "https" {
		parsed.Scheme = "wss"
	} else {
		parsed.Scheme = "ws"
	}
	parsed.Path = "/api/v1/agent-ws/" + c.agentID

	query := parsed.Query()
	query.Set("token", c.token)
	parsed.RawQuery = query.Encode()
	return parsed.String(), nil
}
