//go:build linux

package software

import (
	"bufio"
	"bytes"
	"os/exec"
	"strings"
)

func Collect() []Item {
	if items := collectDpkg(); len(items) > 0 {
		return items
	}
	return collectRpm()
}

func collectDpkg() []Item {
	out, err := exec.Command(
		"dpkg-query", "-W",
		"-f=${Package}\t${Version}\t${Maintainer}\n",
	).Output()
	if err != nil {
		return nil
	}
	var items []Item
	scanner := bufio.NewScanner(bytes.NewReader(out))
	for scanner.Scan() {
		parts := strings.SplitN(scanner.Text(), "\t", 3)
		if len(parts) < 2 || parts[0] == "" {
			continue
		}
		publisher := ""
		if len(parts) == 3 {
			publisher = parts[2]
		}
		items = append(items, Item{
			Name:      parts[0],
			Version:   parts[1],
			Publisher: publisher,
			Source:    "dpkg",
		})
	}
	return items
}

func collectRpm() []Item {
	out, err := exec.Command(
		"rpm", "-qa",
		"--queryformat", "%{NAME}\t%{VERSION}\t%{VENDOR}\n",
	).Output()
	if err != nil {
		return nil
	}
	var items []Item
	scanner := bufio.NewScanner(bytes.NewReader(out))
	for scanner.Scan() {
		parts := strings.SplitN(scanner.Text(), "\t", 3)
		if len(parts) < 1 || parts[0] == "" {
			continue
		}
		version, publisher := "", ""
		if len(parts) >= 2 {
			version = parts[1]
		}
		if len(parts) == 3 {
			publisher = parts[2]
		}
		items = append(items, Item{
			Name:      parts[0],
			Version:   version,
			Publisher: publisher,
			Source:    "rpm",
		})
	}
	return items
}
