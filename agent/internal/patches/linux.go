//go:build linux

package patches

import (
	"bufio"
	"bytes"
	"fmt"
	"os/exec"
	"strings"
)

func Scan() ([]PatchInfo, error) {
	switch {
	case commandExists("apt"):
		return scanApt()
	case commandExists("dnf"):
		return scanDnf()
	case commandExists("yum"):
		return scanYum()
	default:
		return []PatchInfo{}, nil
	}
}

func Install(packages []string) (string, error) {
	switch {
	case commandExists("apt-get"):
		return installApt(packages)
	case commandExists("dnf"):
		return installDnf(packages)
	case commandExists("yum"):
		return installYum(packages)
	default:
		return "", fmt.Errorf("nenhum gerenciador de pacotes suportado encontrado")
	}
}

func commandExists(name string) bool {
	_, err := exec.LookPath(name)
	return err == nil
}

// ─── apt ─────────────────────────────────────────────────────────────────────

func scanApt() ([]PatchInfo, error) {
	// apt list --upgradable pode retornar exit 1 mas ainda produz output válido
	out, _ := exec.Command("apt", "list", "--upgradable", "-qq").Output()

	var result []PatchInfo
	scanner := bufio.NewScanner(bytes.NewReader(out))
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "Listing...") {
			continue
		}

		// Formato: name/channel version arch [upgradable from: old_version]
		parts := strings.Fields(line)
		if len(parts) < 2 {
			continue
		}

		nameChannel := strings.SplitN(parts[0], "/", 2)
		name := nameChannel[0]
		channel := ""
		if len(nameChannel) == 2 {
			channel = nameChannel[1]
		}

		available := parts[1]
		current := extractAptCurrentVersion(line)

		severity := "unknown"
		if strings.Contains(channel, "security") {
			severity = "security"
		}

		result = append(result, PatchInfo{
			Name:             name,
			CurrentVersion:   current,
			AvailableVersion: available,
			Severity:         severity,
			Source:           "apt",
		})
	}
	return result, nil
}

func extractAptCurrentVersion(line string) string {
	const marker = "upgradable from: "
	idx := strings.Index(line, marker)
	if idx == -1 {
		return ""
	}
	rest := line[idx+len(marker):]
	rest = strings.TrimRight(rest, "]")
	return strings.TrimSpace(rest)
}

func installApt(packages []string) (string, error) {
	args := append([]string{"-y", "install", "--only-upgrade"}, packages...)
	cmd := exec.Command("apt-get", args...)
	cmd.Env = []string{
		"DEBIAN_FRONTEND=noninteractive",
		"PATH=/usr/bin:/usr/sbin:/bin:/sbin",
	}
	out, err := cmd.CombinedOutput()
	return string(out), err
}

// ─── dnf ─────────────────────────────────────────────────────────────────────

func scanDnf() ([]PatchInfo, error) {
	// exit 100 = há updates disponíveis (normal)
	out, _ := exec.Command("dnf", "check-update", "--quiet").Output()
	return parseDnfYumOutput(out, "dnf"), nil
}

func installDnf(packages []string) (string, error) {
	args := append([]string{"-y", "upgrade"}, packages...)
	out, err := exec.Command("dnf", args...).CombinedOutput()
	return string(out), err
}

// ─── yum ─────────────────────────────────────────────────────────────────────

func scanYum() ([]PatchInfo, error) {
	out, _ := exec.Command("yum", "check-update", "--quiet").Output()
	return parseDnfYumOutput(out, "yum"), nil
}

func installYum(packages []string) (string, error) {
	args := append([]string{"-y", "update"}, packages...)
	out, err := exec.Command("yum", args...).CombinedOutput()
	return string(out), err
}

func parseDnfYumOutput(out []byte, source string) []PatchInfo {
	var result []PatchInfo
	scanner := bufio.NewScanner(bytes.NewReader(out))
	for scanner.Scan() {
		line := scanner.Text()
		// Linhas de pacote têm 3 colunas: name.arch  version  repo
		// Linhas de metadata começam com espaço ou são cabeçalhos
		if line == "" || line[0] == ' ' || strings.HasPrefix(line, "Last") || strings.HasPrefix(line, "Security") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) < 3 {
			continue
		}

		// name.arch → name
		nameArch := strings.SplitN(parts[0], ".", 2)
		name := nameArch[0]
		available := parts[1]

		result = append(result, PatchInfo{
			Name:             name,
			CurrentVersion:   "",
			AvailableVersion: available,
			Severity:         "unknown",
			Source:           source,
		})
	}
	return result
}
