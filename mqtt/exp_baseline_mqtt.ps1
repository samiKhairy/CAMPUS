param(
    [string]$Devices = "2",
    [int]$PayloadBytes = 100,
    [double]$IntervalSec = 0.1,
    [double]$DurationSec = 60.0,
    [string]$OutputCsv = "results/mqtt_baseline.csv",
    [string]$MqttBroker = "localhost:1883",
    [int]$MqttQos = 1
)

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " RUNNING MQTT BASELINE EXPERIMENT" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Devices      : $Devices"
Write-Host "Payload Size : $PayloadBytes bytes"
Write-Host "Interval     : $IntervalSec s"
Write-Host "Duration     : $DurationSec s"
Write-Host "Output CSV   : $OutputCsv"
Write-Host "MQTT Broker  : $MqttBroker"
Write-Host "MQTT QoS     : $MqttQos"
Write-Host "==================================================" -ForegroundColor Cyan

# Ensure results directory exists
$parentDir = Split-Path -Path $OutputCsv -Parent
if ($parentDir -and !(Test-Path -Path $parentDir)) {
    New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
}

$deviceProcesses = @()
$startedBroker = $false

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

    if ($startedBroker) {
        Write-Host "[RUNNER] Stopping Docker MQTT broker container (mqtt-broker-exp)..." -ForegroundColor Yellow
        docker stop mqtt-broker-exp | Out-Null
        docker rm mqtt-broker-exp | Out-Null
    }
    Write-Host "[RUNNER] Cleanup complete." -ForegroundColor Green
}

try {
    # 1. Start Mosquitto Broker in Docker if not already running
    $runningContainers = docker ps --format '{{.Names}}'
    $brokerRunning = $false
    foreach ($name in $runningContainers) {
        if ($name -eq "mqtt-broker-exp" -or $name -eq "mqtt-broker") {
            $brokerRunning = $true
            break
        }
    }

    if ($brokerRunning) {
        Write-Host "[RUNNER] MQTT broker is already running."
    } else {
        Write-Host "[RUNNER] Starting MQTT broker container in background..." -ForegroundColor Yellow
        $absConfigPath = Join-Path $PSScriptRoot "mosquitto.conf"
        docker run -d --name mqtt-broker-exp -p 1883:1883 -v "${absConfigPath}:/mosquitto/config/mosquitto.conf" eclipse-mosquitto:2 | Out-Null
        $startedBroker = $true
        # Wait for broker to initialize
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
        $psi.Arguments = "src/device_mqtt.py $devId --broker $MqttBroker --qos $MqttQos"
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
    $edgeArgs = "--devices $Devices --payload-size $PayloadBytes --interval $IntervalSec --duration $DurationSec --output $OutputCsv --broker $MqttBroker --qos $MqttQos"
    
    # Run python in the foreground and inherit output stream
    $psiEdge = New-Object System.Diagnostics.ProcessStartInfo
    $psiEdge.FileName = "python"
    $psiEdge.WorkingDirectory = $PSScriptRoot
    $psiEdge.Arguments = "src/edge_mqtt.py $edgeArgs"
    $psiEdge.UseShellExecute = $false
    $psiEdge.RedirectStandardOutput = $false
    $psiEdge.RedirectStandardError = $false
    
    $procEdge = [System.Diagnostics.Process]::Start($psiEdge)
    $procEdge.WaitForExit()
}
finally {
    Cleanup
}
