; 星易查 Windows 安装包脚本（Inno Setup 6）
; 构建（需先跑完 PyInstaller，产物在 dist\星易查\）：
;   ISCC.exe packaging\星易查.iss
; 产物：dist\星易查-Setup.exe
;
; 中文界面语言包（ChineseSimplified.isl，官方未随 Inno Setup 附带）由
; CI / build_windows.bat 下载到本目录；缺失时自动回退英文界面，不影响安装功能。

#define MyAppName "星易查"
#define MyAppFullName "星易查 - 围串标风险识别分析系统"
#define MyAppVersion "2.4.0"
#define MyAppExeName "星易查.exe"

[Setup]
AppId={{9B3A9CB7-DAC7-44F4-B99D-A739014B2B5C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=星易查
UninstallDisplayName={#MyAppFullName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=星易查-Setup
SetupIconFile=star.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
; 避免杀软/兼容性提示：明确声明无签名，不请求在线检查
DisableReadyMemo=no

[Languages]
#if FileExists(AddBackslash(SourcePath) + "ChineseSimplified.isl")
Name: "chinese"; MessagesFile: "ChineseSimplified.isl"
#else
Name: "default"; MessagesFile: "compiler:Default.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式(&D)"; GroupDescription: "附加任务:"

[Files]
Source: "..\dist\星易查\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
function RegSaysLibreOffice(RootKey: Integer): Boolean;
var
  P: String;
begin
  // LibreOffice 把安装目录写进 SOFTWARE\LibreOffice\UNO\InstallPath，
  // 装到 D 盘等自定义目录时只有这里能查到；值名各版本不同
  // （默认值 / Path / InstallPath），三个都试。
  Result := False;
  P := '';
  if RegQueryStringValue(RootKey, 'SOFTWARE\LibreOffice\UNO\InstallPath', '', P) and (P <> '') then Result := True;
  if RegQueryStringValue(RootKey, 'SOFTWARE\LibreOffice\UNO\InstallPath', 'Path', P) and (P <> '') then Result := True;
  if RegQueryStringValue(RootKey, 'SOFTWARE\LibreOffice\UNO\InstallPath', 'InstallPath', P) and (P <> '') then Result := True;
end;

function LibreOfficeDetected: Boolean;
begin
  Result := True;
  if FileExists(ExpandConstant('{autopf64}\LibreOffice\program\soffice.exe')) then Exit;
  if FileExists(ExpandConstant('{autopf32}\LibreOffice\program\soffice.exe')) then Exit;
  if RegSaysLibreOffice(HKLM) then Exit;
  if RegSaysLibreOffice(HKCU) then Exit;
  // 本安装器未开 ArchitecturesInstallIn64BitMode（32 位安装模式），flag-less 的
  // HKLM/HKCU 读的是 32 位视图；64 位 LibreOffice 装在自定义目录时把路径写在
  // 64 位视图（WOW6432Node 才是它的 32 位兄弟）。HKEY_*_64 常量在 32 位
  // Windows 上会内部报错，故用 IsWin64 守卫。
  if IsWin64 and RegSaysLibreOffice(HKEY_LOCAL_MACHINE_64) then Exit;
  if IsWin64 and RegSaysLibreOffice(HKEY_CURRENT_USER_64) then Exit;
  Result := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  // 安装完成后提示 LibreOffice（.doc 正文解析的可选依赖）。
  // 装在自定义目录时注册表有记录，不再误报"未检测到"。
  if (CurStep = ssPostInstall) and not LibreOfficeDetected then
    MsgBox(
      '提示：未检测到 LibreOffice。' + #13#10#13#10 +
      '解析 .doc 格式标书的【正文】时需要 LibreOffice（免费，官网 libreoffice.org 可下载）。' + #13#10 +
      '未安装时将自动跳过 .doc 正文提取，.doc 元数据比对不受影响；' + #13#10 +
      'docx / pdf / 扫描件OCR / xlsx / txt 等功能完全不受影响。' + #13#10 +
      '若已装在非默认位置（如 D 盘），星易查运行时会自动识别注册表记录；' + #13#10 +
      '也可设环境变量 SOFFICE_PATH 指向 soffice.exe 或安装目录。' + #13#10#13#10 +
      '需要时可稍后自行安装 LibreOffice，安装后无需重新安装本软件，重启即可生效。',
      mbInformation, MB_OK);
end;
