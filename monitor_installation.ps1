# Real-time Odoo installation monitor
Write-Host "=== Odoo Installation Monitor ===" -ForegroundColor Cyan
Write-Host "Monitoring: logs\odoo.log" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop monitoring`n" -ForegroundColor Gray

$logFile = "logs\odoo.log"
$lastPosition = 0

if (Test-Path $logFile) {
    # Get initial file size
    $lastPosition = (Get-Item $logFile).Length
    Write-Host "Starting monitoring from current position...`n" -ForegroundColor Green
}

while ($true) {
    if (Test-Path $logFile) {
        $currentSize = (Get-Item $logFile).Length
        
        if ($currentSize -gt $lastPosition) {
            # Read new content
            $file = [System.IO.File]::Open($logFile, 'Open', 'Read', 'ReadWrite')
            $file.Position = $lastPosition
            $reader = New-Object System.IO.StreamReader($file)
            $newContent = $reader.ReadToEnd()
            $reader.Close()
            $file.Close()
            
            # Filter and display relevant lines
            $lines = $newContent -split "`n"
            foreach ($line in $lines) {
                if ($line -match "mesob|install|loading|module|init|creating|updating|error|warning|done" -and $line -notmatch "check_module_update") {
                    # Color code the output
                    if ($line -match "error") {
                        Write-Host $line -ForegroundColor Red
                    } elseif ($line -match "warning") {
                        Write-Host $line -ForegroundColor Yellow
                    } elseif ($line -match "install|creating|init") {
                        Write-Host $line -ForegroundColor Green
                    } elseif ($line -match "loading") {
                        Write-Host $line -ForegroundColor Cyan
                    } elseif ($line -match "done|success") {
                        Write-Host $line -ForegroundColor Magenta
                    } else {
                        Write-Host $line
                    }
                }
            }
            
            $lastPosition = $currentSize
        }
    }
    
    Start-Sleep -Milliseconds 500
}
