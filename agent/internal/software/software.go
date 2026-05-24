// Package software collects the list of installed software on the local machine.
// Collect() is implemented per-platform in windows.go, linux.go, and other.go.
package software

// Item represents a single installed software entry.
type Item struct {
	Name        string `json:"name"`
	Version     string `json:"version"`
	Publisher   string `json:"publisher"`
	InstallDate string `json:"install_date"`
	Source      string `json:"source"`
}
