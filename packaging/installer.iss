; yt-dlp 图形用户界面 —— Inno Setup 安装脚本
;
; 编译：
;   "C:\Program Files\Inno Setup 7\ISCC.exe" packaging\installer.iss
; 依赖：
;   packaging\dist\YtDlpGui\  （先跑 packaging\YtDlpGui.spec 产出）
; 产物：
;   packaging\output\YtDlpGui-1.0.0-setup.exe

#define MyAppName "yt-dlp 图形用户界面"
; 版本号由 packaging/build.py 通过 ISCC 的 /D 参数传入（它从 app/__init__.py 读），
; 直接手编 .iss 时用下面的兜底值。不要试图在 .iss 里解析 Python 源码：
; ISPP 只有 GetStringFileInfo（读 PE 版本资源），没有读文本文件的函数。
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "ytdlp-E"
#define MyAppExeName "YtDlpGui.exe"
; 升级安装时靠这个 GUID 识别「同一个程序」，不要改
#define MyAppId "{{7C4A1F52-9B3E-4E7A-9C21-5D8F0A6B2E14}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\YtDlpGui
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=output
OutputBaseFilename=YtDlpGui-{#MyAppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 装到 Program Files 需要管理员；程序自身只往 %APPDATA% 写数据，不需要提权运行
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\app\assets\app.ico
; 关掉「程序兼容性助手」的兼容性提示
Uninstallable=yes
CloseApplications=yes
RestartApplications=no
AllowNoIcons=yes
DisableDirPage=no
; 许可证页显示 README（含「仅用于个人学习与合法备份」的声明）
LicenseFile=..\README.md

[Languages]
Name: "chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; PyInstaller 的 one-folder 产物整目录带走
Source: "dist\YtDlpGui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"; \
    ValueType: string; ValueName: "{app}\{#MyAppExeName}"; ValueData: "~ WIN10RTM"; \
    Flags: uninsdeletevalue; Check: IsWin10OrNewer

[UninstallDelete]
; 只清程序目录里的残留（%APPDATA% 下的设置/历史属于用户数据，卸载时保留）
Type: filesandordirs; Name: "{app}\bin"
Type: filesandordirs; Name: "{app}\__pycache__"

[Code]
const
  UNINST_KEY = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#MyAppId}_is1';
  { Pascal 里换行符是 #13#10，但它出现在行首会被 Inno 预处理器当成 # 指令，
    因此统一收进常量，正文里只写 CRLF }
  CRLF = #13#10;

function IsWin10OrNewer: Boolean;
begin
  Result := (GetWindowsVersion >= $0A000000);
end;

{ 程序在跑的时候覆盖会「文件被占用」，先拦一道。
  更精确的「正在运行」检测交给 Inno 的 CloseApplications（[Setup] 里已开）。 }
function InitializeSetup: Boolean;
begin
  Result := True;
  if FindWindowByWindowName('{#MyAppName}') <> 0 then
  begin
    MsgBox('{#MyAppName} 正在运行，请先退出后再安装。', mbError, MB_OK);
    Result := False;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\YtDlpGui');
    if DirExists(DataDir) then
    begin
      if MsgBox('是否一并删除程序数据？' + CRLF + CRLF +
                '包含下载设置、历史记录、登录凭据、封面缓存与已下载的 yt-dlp 组件：' + CRLF +
                DataDir + CRLF + CRLF +
                '选择「否」则保留，下次安装还能继续用。',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    { 首次启动会从 PyPI 取 yt-dlp，装完提示一下，免得用户以为是卡住 }
    if not WizardSilent then
      MsgBox('安装完成。' + CRLF + CRLF +
             '首次启动时程序会联网获取下载引擎 yt-dlp（几秒钟），' +
             '之后可在「设置 → 组件」里随时更新；FFmpeg 也可在同一页安装，' +
             '或指定你已安装的路径。', mbInformation, MB_OK);
  end;
end;
