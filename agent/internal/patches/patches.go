// Package patches detecta e instala atualizações de SO.
// Scan() e Install() são implementados por linux.go, windows.go e other.go.
package patches

// PatchInfo representa um pacote/atualização disponível.
type PatchInfo struct {
	Name             string `json:"name"`
	CurrentVersion   string `json:"current_version"`
	AvailableVersion string `json:"available_version"`
	Severity         string `json:"severity"` // security, unknown
	Source           string `json:"source"`   // apt, dnf, yum, windows
}
