param(
    [string]$Devices = "2",
    [int]$PayloadBytes = 100,
    [double]$IntervalSec = 0.1,
    [double]$DurationSec = 60.0,
    [string]$OutputCsv = "results/zenoh_baseline.csv",
    [string]$ZenohRouter = "tcp/localhost:7447"
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " RUNNING ZENOH BASELINE EXPERIMENT" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Devices      : $Devices"
Write-Host "Payload Size : $PayloadBytes bytes"
Write-Host "Interval     : $IntervalSec s"
Write-Host "Duration     : $DurationSec s"
Write-Host "Output CSV   : $OutputCsv"
Write-Host "Zenoh Router : $ZenohRouter"
Write-Host "==================================================" -ForegroundColor Cyan

# Ensure results directory exists
$parentDir = Split-Path -Path $OutputCsv -Parent
if ($parentDir -and !(Test-Path -Path $parentDir)) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
}

$deviceProcesses = @()
$startedRouter = $false

function Cleanup {
    Write-Host "`n[RUNNER] Terminating background simulator processes..." -ForegroundColor Yellow
    foreach ($proc in $deviceProcesses) {
        if (!$proc.HasExited) {
            Write-Host "  -> Killing device process (PID: $($proc.Id))..."
            try {
                $proc.Kill()
                $proc.WaitForExit(2000) | Out-Null
            } catch {
                # Ignore errors on cleanup
            }
        }
    }

    if ($startedRouter) {
        Write-Host "[RUNNER] Stopping Docker Zenoh router container (zenoh-router-exp)..." -ForegroundColor Yellow
        docker stop zenoh-router-exp | Out-Null
        docker rm zenoh-router-exp | Out-Null
    }
    Write-Host "[RUNNER] Cleanup complete." -ForegroundColor Green
}

try {
    # 1. Start Zenoh Router in Docker if not already running
    $runningContainers = docker ps --format '{{.Names}}'
    $routerRunning = $false
    foreach ($name in $runningContainers) {
        if ($name -eq "zenoh-router-exp" -or $name -eq "zenoh-router") {
            $routerRunning = $true
            break
        }
    }

    if ($routerRunning) {
        Write-Host "[RUNNER] Zenoh router is already running."
    } else {
        Write-Host "[RUNNER] Starting Zenoh router container in background..." -ForegroundColor Yellow
        docker run -d --name zenoh-router-exp -p 7447:7447 eclipse/zenoh:latest | Out-Null
        $startedRouter = $true
        # Wait for router to initialize
        Start-Sleep -Seconds 2
    }

    # Resolve target device count or names
    $targetDevs = @()
    if ($Devices -as [int]) {
        $numDevs = [int]$Devices
        for ($i = 1; $i -le $numDevs; $i++) {
            $targetDevs += "device-$i"
        }
    } else {
        $targetDevs = $Devices.Split(",")
    }

    # 2. Start Device simulators in background
    Write-Host "[RUNNER] Launching $($targetDevs.Count) device simulators..." -ForegroundColor Yellow
    foreach ($devId in $targetDevs) {
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = "python"
        $psi.WorkingDirectory = $PSScriptRoot
        $psi.Arguments = "src/device_zenoh.py $devId --router $ZenohRouter"
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        
        $proc = [System.Diagnostics.Process]::Start($psi)
        $deviceProcesses += $proc
        Write-Host "  -> Started $devId (PID: $($proc.Id))"
    }

    # Wait for devices to connect and subscribe
    Start-Sleep -Seconds 1

    # 3. Run Edge Node
    Write-Host "[RUNNER] Starting Edge Node..." -ForegroundColor Yellow
    $edgeArgs = "--devices $Devices --payload-size $PayloadBytes --interval $IntervalSec --duration $DurationSec --output $OutputCsv --router $ZenohRouter"
    
    # Run python in the foreground and inherit output stream
    $psiEdge = New-Object System.Diagnostics.ProcessStartInfo
    $psiEdge.FileName = "python"
    $psiEdge.WorkingDirectory = $PSScriptRoot
    $psiEdge.Arguments = "src/edge_zenoh.py $edgeArgs"
    $psiEdge.UseShellExecute = $false
    $psiEdge.RedirectStandardOutput = $false
    $psiEdge.RedirectStandardError = $false
    
    $procEdge = [System.Diagnostics.Process]::Start($psiEdge)
    $procEdge.WaitForExit()
}
finally {
    Cleanup
}
