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
)

const reconnectDelay = 10 * time.Second

type Client struct {
	serverURL string
	token     string
	agentID   string
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
	for {
		_, data, err := conn.ReadMessage()
		if err != nil {
			return err
		}

		var command ScriptCommand
		if err := json.Unmarshal(data, &command); err != nil {
			log.Printf("Comando inválido recebido: %v", err)
			continue
		}
		if command.Type != "run_script" {
			continue
		}

		writeMu.Lock()
		err = conn.WriteJSON(map[string]string{
			"type":         "script_started",
			"execution_id": command.ExecutionID,
		})
		writeMu.Unlock()
		if err != nil {
			return err
		}

		go func(cmd ScriptCommand) {
			result := Execute(ctx, cmd)
			writeMu.Lock()
			err := conn.WriteJSON(result)
			writeMu.Unlock()
			if err != nil {
				log.Printf("Erro ao enviar resultado de script: %v", err)
			}
		}(command)
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
