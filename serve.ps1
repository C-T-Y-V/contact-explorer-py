<#
.SYNOPSIS
    Runs the Contact Explorer REST API Server on Windows.
.EXAMPLE
    .\serve.ps1
    .\serve.ps1 -Port 8080 -Host "0.0.0.0"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$HostName = "127.0.0.1",

    [Parameter(Mandatory=$false)]
    [int]$Port = 8765,

    [Parameter(Mandatory=$false)]
    [string]$DatabasePath
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

$argsList = @("--host", $HostName, "--port", $Port)
if ($DatabasePath) {
    $argsList += @("--db", $DatabasePath)
}

python serve.py @argsList
