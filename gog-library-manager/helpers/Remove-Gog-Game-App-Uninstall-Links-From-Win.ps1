#Requires -RunAsAdministrator
param(
    [switch]$y
)

$uninstallPath = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
$keysFound = 0
$keysDeleted = 0
$keysSkipped = 0

$subkeys = Get-ChildItem -Path $uninstallPath
foreach ($subkey in $subkeys) {
    try {
        $urlInfoAbout = (Get-ItemProperty -Path $subkey.PSPath).UrlInfoAbout
        if ($urlInfoAbout -eq "http://www.gog.com") {
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

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "  GOG registry keys found: $keysFound" -ForegroundColor White
Write-Host "  GOG registry keys deleted: $keysDeleted" -ForegroundColor White
if ($keysSkipped -gt 0) {
    Write-Host "  GOG registry keys skipped: $keysSkipped" -ForegroundColor White
}

if ($keysFound -eq 0) {
    Write-Host "No GOG uninstall registry keys found." -ForegroundColor Green
}

Write-Host "Exiting script in 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
exit
