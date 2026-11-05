@echo off
rem Startup launcher for the Windows oracle agent.
rem Lives in the Startup folder of the auto-logon user so the agent runs in
rem the interactive desktop session, which is the only place Word COM works.
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\work\agent\OracleAgent.ps1" >> "C:\work\agent\launcher.log" 2>&1
