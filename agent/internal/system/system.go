// Package system encapsula coleta de informações do sistema operacional.
package system

import (
	"fmt"
	"runtime"
	"time"

	"github.com/shirou/gopsutil/v3/cpu"
	"github.com/shirou/gopsutil/v3/disk"
	"github.com/shirou/gopsutil/v3/host"
	"github.com/shirou/gopsutil/v3/mem"
)

type SystemInfo struct {
	Hostname     string
	OS           string
	Platform     string
	Architecture string
	KernelArch   string
	Uptime       uint64
	CPUModel     string
	CPUCores     int
	RAMTotal     uint64
	DiskTotal    uint64
}

type SystemMetrics struct {
	Hostname  string
	CPUUsage  float64
	RAMUsage  float64
	DiskUsage float64
	Uptime    uint64
}

func diskPath() string {
	if runtime.GOOS == "windows" {
		return "C:\\"
	}
	return "/"
}

func CollectInfo() (*SystemInfo, error) {
	hostInfo, err := host.Info()
	if err != nil {
		return nil, fmt.Errorf("host info: %w", err)
	}

	cpuInfo, err := cpu.Info()
	if err != nil {
		return nil, fmt.Errorf("cpu info: %w", err)
	}

	memInfo, err := mem.VirtualMemory()
	if err != nil {
		return nil, fmt.Errorf("mem info: %w", err)
	}

	diskInfo, err := disk.Usage(diskPath())
	if err != nil {
		return nil, fmt.Errorf("disk info: %w", err)
	}

	cpuModel := "unknown"
	cpuCores := runtime.NumCPU()
	if len(cpuInfo) > 0 {
		cpuModel = cpuInfo[0].ModelName
		total := 0
		for _, c := range cpuInfo {
			total += int(c.Cores)
		}
		if total > cpuCores {
			cpuCores = total
		}
	}

	return &SystemInfo{
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
	}, nil
}

func CollectMetrics() (*SystemMetrics, error) {
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

	diskInfo, err := disk.Usage(diskPath())
	if err != nil {
		return nil, err
	}

	return &SystemMetrics{
		Hostname:  hostInfo.Hostname,
		CPUUsage:  cpuUsage,
		RAMUsage:  memInfo.UsedPercent,
		DiskUsage: diskInfo.UsedPercent,
		Uptime:    hostInfo.Uptime,
	}, nil
}
