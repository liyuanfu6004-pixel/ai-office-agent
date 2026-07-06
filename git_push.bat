@echo off
chcp 65001 >nul

echo ============================
echo AI Office Agent Git Auto Push
echo ============================

echo.
echo [1/4] 添加文件...
git add .

echo.
echo [2/4] 输入提交说明：
set /p msg=请输入commit信息：

if "%msg%"=="" set msg=auto update

echo.
echo [3/4] 提交代码...
git commit -m "%msg%"

echo.
echo [4/4] 推送到GitHub...
git push

echo.
echo ===== 完成 =====
pause