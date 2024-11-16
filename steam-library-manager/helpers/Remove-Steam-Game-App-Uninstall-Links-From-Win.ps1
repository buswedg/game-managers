#Requires -RunAsAdministrator

$registryPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\",
    "HKLM:\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\"
)

foreach ($path in $registryPaths) {
    $subkeys = Get-ChildItem -Path $path

    foreach ($subkey in $subkeys) {
        $uninstallString = (Get-ItemProperty -Path $subkey.PSPath).UninstallString
        if ($uninstallString -like "*steam://uninstall/*") {
            $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
            if ($choice -eq "Y") {
                Write-Host "Deleting key $($subkey.PSPath)"
                Remove-Item -Path $subkey.PSPath -Force
            }
        }
    }
}

Write-Host "Exiting script in 5 seconds."; Start-Sleep -Seconds 5
exit