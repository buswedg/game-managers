#Requires -RunAsAdministrator

$uninstallPath = "Registry::HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"

$subkeys = Get-ChildItem -Path $uninstallPath
foreach ($subkey in $subkeys) {
    try {
        $urlInfoAbout = (Get-ItemProperty -Path $subkey.PSPath).UrlInfoAbout
        if ($urlInfoAbout -eq "http://www.gog.com") {
            $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
            if ($choice -eq "Y") {
                Write-Host "Deleting key $($subkey.PSPath)"
                Remove-Item -Path $subkey.PSPath -Force
            }
        }
    } catch {
        Write-Host "Error reading key $($subkey.PSPath). Skipping."
    }
}

Write-Host "Exiting script in 5 seconds."; Start-Sleep -Seconds 5
exit
