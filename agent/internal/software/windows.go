//go:build windows

package software

import "golang.org/x/sys/windows/registry"

var uninstallPaths = []string{
	`SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall`,
	`SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall`,
}

func Collect() []Item {
	seen := map[string]bool{}
	var items []Item
	for _, path := range uninstallPaths {
		k, err := registry.OpenKey(registry.LOCAL_MACHINE, path, registry.READ)
		if err != nil {
			continue
		}
		items = collectFromKey(k, seen, items)
		k.Close()
	}
	return items
}

func collectFromKey(k registry.Key, seen map[string]bool, items []Item) []Item {
	subkeys, err := k.ReadSubKeyNames(-1)
	if err != nil {
		return items
	}
	for _, sub := range subkeys {
		sk, err := registry.OpenKey(k, sub, registry.READ)
		if err != nil {
			continue
		}
		name, _, _ := sk.GetStringValue("DisplayName")
		version, _, _ := sk.GetStringValue("DisplayVersion")
		publisher, _, _ := sk.GetStringValue("Publisher")
		installDate, _, _ := sk.GetStringValue("InstallDate")
		sk.Close()

		if name == "" || seen[name] {
			continue
		}
		seen[name] = true
		items = append(items, Item{
			Name:        name,
			Version:     version,
			Publisher:   publisher,
			InstallDate: installDate,
			Source:      "windows_registry",
		})
	}
	return items
}
