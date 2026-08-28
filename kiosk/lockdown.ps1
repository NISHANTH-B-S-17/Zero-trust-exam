param (
    [switch]$Restore
)

# Registry paths
$sysPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\System"
$expPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"

# Ensure paths exist
if (!(Test-Path $sysPath)) {
    New-Item -Path $sysPath -Force | Out-Null
}
if (!(Test-Path $expPath)) {
    New-Item -Path $expPath -Force | Out-Null
}

Write-Host "Nivasha Kiosk Lockdown Script" -ForegroundColor Cyan
Write-Host "WARNING: This script modifies Current User policies. Administrator approval may be required depending on UAC." -ForegroundColor Yellow
Write-Host ""

if ($Restore) {
    Write-Host "Running in RESTORE mode..." -ForegroundColor Green
    
    # Remove restrictions
    Write-Host "Removing DisableTaskMgr..."
    Remove-ItemProperty -Path $sysPath -Name "DisableTaskMgr" -ErrorAction SilentlyContinue
    
    Write-Host "Removing DisableLockWorkstation..."
    Remove-ItemProperty -Path $sysPath -Name "DisableLockWorkstation" -ErrorAction SilentlyContinue
    
    Write-Host "Removing DisableChangePassword..."
    Remove-ItemProperty -Path $sysPath -Name "DisableChangePassword" -ErrorAction SilentlyContinue
    
    Write-Host "Removing NoLogoff..."
    Remove-ItemProperty -Path $expPath -Name "NoLogoff" -ErrorAction SilentlyContinue
    
    Write-Host ""
    Write-Host "Policies restored successfully. You may need to log off and log back in or restart explorer.exe for changes to take effect." -ForegroundColor Green
} else {
    Write-Host "Running in LOCKDOWN mode..." -ForegroundColor Red
    
    # Apply restrictions
    Write-Host "Setting DisableTaskMgr = 1..."
    Set-ItemProperty -Path $sysPath -Name "DisableTaskMgr" -Value 1 -Type DWord
    
    Write-Host "Setting DisableLockWorkstation = 1..."
    Set-ItemProperty -Path $sysPath -Name "DisableLockWorkstation" -Value 1 -Type DWord
    
    Write-Host "Setting DisableChangePassword = 1..."
    Set-ItemProperty -Path $sysPath -Name "DisableChangePassword" -Value 1 -Type DWord
    
    Write-Host "Setting NoLogoff = 1..."
    Set-ItemProperty -Path $expPath -Name "NoLogoff" -Value 1 -Type DWord
    
    Write-Host ""
    Write-Host "Lockdown policies applied successfully. (Note: These are HKCU settings only. True kiosk mode requires Assigned Access)." -ForegroundColor Green
}
