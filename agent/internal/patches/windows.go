//go:build windows

package patches

import (
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
)

const scanPS = `
$ErrorActionPreference = 'Stop'
try {
    $Session  = New-Object -ComObject Microsoft.Update.Session
    $Searcher = $Session.CreateUpdateSearcher()
    $Result   = $Searcher.Search("IsInstalled=0 and Type='Software'")
    $List = @()
    foreach ($U in $Result.Updates) {
        $sev = if ($U.MsrcSeverity) { $U.MsrcSeverity.ToLower() } else { "unknown" }
        $List += [PSCustomObject]@{
            name              = $U.Title
            current_version   = ""
            available_version = $U.Identity.UpdateID
            severity          = $sev
            source            = "windows"
        }
    }
    $List | ConvertTo-Json -Depth 2
} catch {
    Write-Error $_.Exception.Message
    exit 1
}
`

const installPS = `
param([string[]]$Packages)
$ErrorActionPreference = 'Stop'
$Session  = New-Object -ComObject Microsoft.Update.Session
$Searcher = $Session.CreateUpdateSearcher()
$Result   = $Searcher.Search("IsInstalled=0 and Type='Software'")
$Col = New-Object -ComObject Microsoft.Update.UpdateColl
foreach ($U in $Result.Updates) {
    if (-not $U.EulaAccepted) { $U.AcceptEula() }
    $Col.Add($U) | Out-Null
}
if ($Col.Count -eq 0) {
    Write-Output "Nenhuma atualização pendente."
    exit 0
}
$DL = $Session.CreateUpdateDownloader()
$DL.Updates = $Col
$DL.Download() | Out-Null
$Inst = $Session.CreateUpdateInstaller()
$Inst.Updates = $Col
$R = $Inst.Install()
Write-Output "Instalados: $($Col.Count). Reboot necessário: $($R.RebootRequired)"
`

func Scan() ([]PatchInfo, error) {
	out, err := runPS(scanPS)
	if err != nil {
		return nil, fmt.Errorf("scan Windows Update: %w", err)
	}
	out = strings.TrimSpace(out)
	if out == "" || out == "null" {
		return []PatchInfo{}, nil
	}
	var patches []PatchInfo
	if err := json.Unmarshal([]byte(out), &patches); err != nil {
		// PS pode retornar objeto único (não array) se só há 1 update
		var single PatchInfo
		if err2 := json.Unmarshal([]byte(out), &single); err2 == nil {
			return []PatchInfo{single}, nil
		}
		return []PatchInfo{}, nil
	}
	return patches, nil
}

func Install(packages []string) (string, error) {
	out, err := runPS(installPS)
	return out, err
}

func runPS(script string) (string, error) {
	cmd := exec.Command("powershell.exe",
		"-NoProfile", "-NonInteractive",
		"-ExecutionPolicy", "Bypass",
		"-Command", script,
	)
	out, err := cmd.Output()
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return "", fmt.Errorf("%w: %s", err, string(ee.Stderr))
		}
	}
	return string(out), err
}
