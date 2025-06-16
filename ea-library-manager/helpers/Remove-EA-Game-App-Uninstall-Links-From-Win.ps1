#Requires -RunAsAdministrator
param(
    [switch]$y
)

$registryPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\",
    "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\"
)

$keysFound = 0
$keysDeleted = 0
$keysSkipped = 0

foreach ($path in $registryPaths) {
    $subkeys = Get-ChildItem -Path $path
    foreach ($subkey in $subkeys) {
        try {
            $uninstallString = (Get-ItemProperty -Path $subkey.PSPath).UninstallString
            if ($uninstallString -like "*EAInstaller*") {
                $keysFound++
                
                if ($y) {
                    Write-Host "Auto-deleting key $($subkey.PSPath)" -ForegroundColor Yellow
                    Remove-Item -Path $subkey.PSPath -Force
                    $keysDeleted++
                } else {
                    $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
                    if ($choice -eq "Y") {
                        Write-Host "Deleting key $($subkey.PSPath)" -ForegroundColor Green
                        Remove-Item -Path $subkey.PSPath -Force
                        $keysDeleted++
                    } else {
                        Write-Host "Skipped key $($subkey.PSPath)" -ForegroundColor Gray
                        $keysSkipped++
                    }
                }
            }
        } catch {
            Write-Host "Error reading key $($subkey.PSPath). Skipping." -ForegroundColor Red
        }
    }
}

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "  EA registry keys found: $keysFound" -ForegroundColor White
Write-Host "  EA registry keys deleted: $keysDeleted" -ForegroundColor White
if ($keysSkipped -gt 0) {
    Write-Host "  EA registry keys skipped: $keysSkipped" -ForegroundColor White
}

if ($keysFound -eq 0) {
    Write-Host "No EA uninstall registry keys found." -ForegroundColor Green
}

Write-Host "Exiting script in 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
exit
