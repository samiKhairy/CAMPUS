param(
    [string]$Devices = "2",
    [int]$PayloadBytes = 100,
    [double]$IntervalSec = 0.1,
    [double]$DurationSec = 60.0,
    [string]$OutputCsv = "results/grpc_baseline.csv",
    [string]$GrpcServer = "localhost:50051"
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " RUNNING GRPC BASELINE EXPERIMENT" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Devices      : $Devices"
Write-Host "Payload Size : $PayloadBytes bytes"
Write-Host "Interval     : $IntervalSec s"
Write-Host "Duration     : $DurationSec s"
Write-Host "Output CSV   : $OutputCsv"
Write-Host "gRPC Server  : $GrpcServer"
Write-Host "==================================================" -ForegroundColor Cyan

# Parse server port from endpoint (e.g. localhost:50051 -> 50051)
$port = "50051"
if ($GrpcServer -like "*:*") {
    $port = $GrpcServer.Split(":")[-1]
}

# Ensure results directory exists
$parentDir = Split-Path -Path $OutputCsv -Parent
if ($parentDir -and !(Test-Path -Path $parentDir)) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
}

$deviceProcesses = @()
$serverProcess = $null

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

    if ($serverProcess -and !$serverProcess.HasExited) {
        Write-Host "[RUNNER] Stopping gRPC server process (PID: $($serverProcess.Id))..." -ForegroundColor Yellow
        try {
            $serverProcess.Kill()
        } catch {}
    }
    Write-Host "[RUNNER] Cleanup complete." -ForegroundColor Green
}

try {
    # 1. Start gRPC Server in the background first
    Write-Host "[RUNNER] Starting gRPC Server..." -ForegroundColor Yellow
    $psiServer = New-Object System.Diagnostics.ProcessStartInfo
    $psiServer.FileName = "python"
    $psiServer.WorkingDirectory = $PSScriptRoot
    $psiServer.Arguments = "server.py --port $port --devices $Devices --payload-size $PayloadBytes --interval $IntervalSec --duration $DurationSec --output $OutputCsv"
    $psiServer.UseShellExecute = $false
    # We do NOT redirect streams to keep standard output printing to the host terminal
    $psiServer.RedirectStandardOutput = $false
    $psiServer.RedirectStandardError = $false
    
    $serverProcess = [System.Diagnostics.Process]::Start($psiServer)
    Write-Host "  -> Started Server (PID: $($serverProcess.Id))"

    # Wait for server to bind and listen
    Start-Sleep -Seconds 2

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
        $psi.Arguments = "client.py $devId --server $GrpcServer"
        $psi.UseShellExecute = $false
        $psi.CreateNoWindow = $true
        
        $proc = [System.Diagnostics.Process]::Start($psi)
        $deviceProcesses += $proc
        Write-Host "  -> Started $devId (PID: $($proc.Id))"
    }

    # 3. Wait for the server process to complete
    $serverProcess.WaitForExit()
}
finally {
    Cleanup
}
