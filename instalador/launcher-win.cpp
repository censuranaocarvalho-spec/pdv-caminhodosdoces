#define UNICODE
#define _UNICODE
#include <winsock2.h>
#include <windows.h>
#include <shellapi.h>
#include <tlhelp32.h>
#include <stdio.h>

static wchar_t g_raiz[MAX_PATH];
static wchar_t g_python[MAX_PATH];
static wchar_t g_main[MAX_PATH];
static HWND g_status;
static HBITMAP g_logo;

static void juntar(wchar_t *destino, int n, const wchar_t *a, const wchar_t *b) {
    _snwprintf(destino, n, L"%s\\%s", a, b);
}

static int existe(const wchar_t *caminho) {
    return GetFileAttributesW(caminho) != INVALID_FILE_ATTRIBUTES;
}

static void achar_raiz(void) {
    wchar_t exe[MAX_PATH];
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    wchar_t *barra = wcsrchr(exe, L'\\');
    if (barra) *barra = 0;
    juntar(g_main, MAX_PATH, exe, L"main.py");
    if (existe(g_main)) {
        lstrcpynW(g_raiz, exe, MAX_PATH);
        return;
    }
    barra = wcsrchr(exe, L'\\');
    if (barra) *barra = 0;
    lstrcpynW(g_raiz, exe, MAX_PATH);
    juntar(g_main, MAX_PATH, g_raiz, L"main.py");
}

static void caminho_python(void) {
    juntar(g_python, MAX_PATH, g_raiz, L"core-orders\\venv\\Scripts\\python.exe");
}

static void definir_status(const wchar_t *texto) {
    if (g_status) SetWindowTextW(g_status, texto);
}

static int rodar_e_esperar(const wchar_t *comando, const wchar_t *pasta, int janela) {
    STARTUPINFOW info;
    PROCESS_INFORMATION proc;
    wchar_t linha[2048];
    ZeroMemory(&info, sizeof info);
    ZeroMemory(&proc, sizeof proc);
    info.cb = sizeof info;
    info.dwFlags = STARTF_USESHOWWINDOW;
    info.wShowWindow = janela ? SW_SHOWNORMAL : SW_HIDE;
    lstrcpynW(linha, comando, 2048);
    if (!CreateProcessW(NULL, linha, NULL, NULL, FALSE, janela ? CREATE_NEW_CONSOLE : CREATE_NO_WINDOW, NULL, pasta, &info, &proc)) {
        return 0;
    }
    WaitForSingleObject(proc.hProcess, 600000);
    DWORD codigo = 1;
    GetExitCodeProcess(proc.hProcess, &codigo);
    CloseHandle(proc.hProcess);
    CloseHandle(proc.hThread);
    return codigo == 0;
}

static int preparar(void) {
    if (existe(g_python)) return 1;
    wchar_t sistema[MAX_PATH];
    if (!SearchPathW(NULL, L"python.exe", NULL, MAX_PATH, sistema, NULL)) {
        MessageBoxW(NULL, L"Falta o Python neste computador.\nNa instala\u00e7\u00e3o, marque Add python.exe to PATH.", L"Caminho dos Doces", MB_OK | MB_ICONINFORMATION);
        return 0;
    }
    definir_status(L"Preparando o programa. Pode demorar um pouco.");
    wchar_t cmd[2048];
    _snwprintf(cmd, 2048, L"\"%s\" -m venv \"%s\\core-orders\\venv\"", sistema, g_raiz);
    if (!rodar_e_esperar(cmd, g_raiz, 1)) return 0;
    _snwprintf(cmd, 2048, L"\"%s\" -m pip install fastapi uvicorn pydantic websocket-client", g_python);
    return rodar_e_esperar(cmd, g_raiz, 1);
}

static int processo_do_pdv(DWORD *pid) {
    HANDLE foto = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    PROCESSENTRY32W item;
    int achou = 0;
    if (foto == INVALID_HANDLE_VALUE) return 0;
    item.dwSize = sizeof item;
    if (Process32FirstW(foto, &item)) {
        do {
            HANDLE proc = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, item.th32ProcessID);
            if (!proc) continue;
            wchar_t imagem[MAX_PATH];
            DWORD n = MAX_PATH;
            if (QueryFullProcessImageNameW(proc, 0, imagem, &n) && _wcsicmp(imagem, g_python) == 0) {
                *pid = item.th32ProcessID;
                achou = 1;
                CloseHandle(proc);
                break;
            }
            CloseHandle(proc);
        } while (Process32NextW(foto, &item));
    }
    CloseHandle(foto);
    return achou;
}

static int pagina_no_ar(void) {
    SOCKET soquete = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    sockaddr_in endereco;
    u_long modo = 1;
    if (soquete == INVALID_SOCKET) return 0;
    ioctlsocket(soquete, FIONBIO, &modo);
    ZeroMemory(&endereco, sizeof endereco);
    endereco.sin_family = AF_INET;
    endereco.sin_port = htons(8090);
    endereco.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    connect(soquete, (sockaddr *)&endereco, sizeof endereco);
    fd_set grupo;
    timeval espera;
    FD_ZERO(&grupo);
    FD_SET(soquete, &grupo);
    espera.tv_sec = 0;
    espera.tv_usec = 200000;
    int pronto = select(0, NULL, &grupo, NULL, &espera) > 0;
    closesocket(soquete);
    return pronto;
}

static int esperar_pagina(void) {
    for (int i = 0; i < 40; i++) {
        if (pagina_no_ar()) return 1;
        Sleep(500);
    }
    return 0;
}

static int git_caminho(wchar_t *destino) {
    if (SearchPathW(NULL, L"git.exe", NULL, MAX_PATH, destino, NULL)) return 1;
    wchar_t programas[MAX_PATH];
    if (!GetEnvironmentVariableW(L"ProgramFiles", programas, MAX_PATH)) return 0;
    _snwprintf(destino, MAX_PATH, L"%s\\Git\\cmd\\git.exe", programas);
    return existe(destino);
}

static int git_texto(const wchar_t *argumentos, wchar_t *saida, int n) {
    wchar_t git[MAX_PATH];
    wchar_t cmd[2048];
    HANDLE leitura, escrita;
    SECURITY_ATTRIBUTES seguranca;
    STARTUPINFOW info;
    PROCESS_INFORMATION proc;
    if (!git_caminho(git)) return 0;
    ZeroMemory(&seguranca, sizeof seguranca);
    seguranca.nLength = sizeof seguranca;
    seguranca.bInheritHandle = TRUE;
    if (!CreatePipe(&leitura, &escrita, &seguranca, 0)) return 0;
    SetHandleInformation(leitura, HANDLE_FLAG_INHERIT, 0);
    ZeroMemory(&info, sizeof info);
    ZeroMemory(&proc, sizeof proc);
    info.cb = sizeof info;
    info.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    info.hStdOutput = escrita;
    info.hStdError = escrita;
    info.wShowWindow = SW_HIDE;
    _snwprintf(cmd, 2048, L"\"%s\" -C \"%s\" %s", git, g_raiz, argumentos);
    if (!CreateProcessW(NULL, cmd, NULL, NULL, TRUE, CREATE_NO_WINDOW, NULL, g_raiz, &info, &proc)) {
        CloseHandle(leitura);
        CloseHandle(escrita);
        return 0;
    }
    CloseHandle(escrita);
    char bruto[512];
    DWORD lido = 0;
    ReadFile(leitura, bruto, sizeof bruto - 1, &lido, NULL);
    bruto[lido] = 0;
    WaitForSingleObject(proc.hProcess, 25000);
    DWORD codigo = 1;
    GetExitCodeProcess(proc.hProcess, &codigo);
    CloseHandle(proc.hProcess);
    CloseHandle(proc.hThread);
    CloseHandle(leitura);
    MultiByteToWideChar(CP_UTF8, 0, bruto, -1, saida, n);
    return codigo == 0;
}

static void confirmar_atualizacao(void) {
    wchar_t gitdir[MAX_PATH];
    wchar_t local[80];
    wchar_t remoto[80];
    juntar(gitdir, MAX_PATH, g_raiz, L".git");
    if (!existe(gitdir)) return;
    if (!git_texto(L"fetch origin", local, 80)) return;
    if (!git_texto(L"rev-parse HEAD", local, 80)) return;
    if (!git_texto(L"rev-parse @{upstream}", remoto, 80)) return;
    wchar_t *fim_local = wcspbrk(local, L"\r\n");
    wchar_t *fim_remoto = wcspbrk(remoto, L"\r\n");
    if (fim_local) *fim_local = 0;
    if (fim_remoto) *fim_remoto = 0;
    if (wcscmp(local, remoto) == 0) return;
    int resposta = MessageBoxW(NULL,
        L"Chegou atualiza\u00e7\u00e3o do PDV.\n\nPode atualizar agora?",
        L"Caminho dos Doces",
        MB_YESNO | MB_ICONQUESTION | MB_TOPMOST);
    if (resposta != IDYES) return;
    definir_status(L"Atualizando...");
    git_texto(L"pull --ff-only origin main", local, 80);
}

static void ligar(void) {
    DWORD pid = 0;
    if (!existe(g_main)) {
        MessageBoxW(NULL, L"N\u00e3o achei o programa. Deixe este execut\u00e1vel dentro da pasta do PDV.", L"Caminho dos Doces", MB_OK | MB_ICONINFORMATION);
        return;
    }
    confirmar_atualizacao();
    if (!preparar()) {
        definir_status(L"O PDV n\u00e3o foi preparado.");
        return;
    }
    if (!processo_do_pdv(&pid)) {
        STARTUPINFOW info;
        PROCESS_INFORMATION proc;
        wchar_t cmd[2048];
        wchar_t logs[MAX_PATH];
        ZeroMemory(&info, sizeof info);
        ZeroMemory(&proc, sizeof proc);
        info.cb = sizeof info;
        info.dwFlags = STARTF_USESHOWWINDOW;
        info.wShowWindow = SW_HIDE;
        juntar(logs, MAX_PATH, g_raiz, L"logs");
        CreateDirectoryW(logs, NULL);
        _snwprintf(cmd, 2048, L"\"%s\" \"%s\"", g_python, g_main);
        definir_status(L"Ligando em segundo plano...");
        if (!CreateProcessW(NULL, cmd, NULL, NULL, FALSE, CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP, NULL, g_raiz, &info, &proc)) {
            definir_status(L"O PDV n\u00e3o ligou.");
            return;
        }
        CloseHandle(proc.hProcess);
        CloseHandle(proc.hThread);
        if (!esperar_pagina()) {
            definir_status(L"O PDV n\u00e3o abriu.");
            return;
        }
    }
    ShellExecuteW(NULL, L"open", L"http://127.0.0.1:8090/", NULL, NULL, SW_SHOWNORMAL);
    definir_status(L"O PDV est\u00e1 ligado, em segundo plano.");
}

static void desligar(void) {
    DWORD pid = 0;
    if (!processo_do_pdv(&pid)) {
        definir_status(L"O PDV est\u00e1 desligado.");
        return;
    }
    HANDLE proc = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
    if (proc) {
        TerminateProcess(proc, 0);
        CloseHandle(proc);
    }
    definir_status(L"O PDV est\u00e1 desligado.");
}

static LRESULT CALLBACK janela(HWND hwnd, UINT msg, WPARAM wparam, LPARAM lparam) {
    switch (msg) {
    case WM_CREATE: {
        wchar_t logo[MAX_PATH];
        juntar(logo, MAX_PATH, g_raiz, L"instalador\\logo.bmp");
        g_logo = (HBITMAP)LoadImageW(NULL, logo, IMAGE_BITMAP, 0, 0, LR_LOADFROMFILE);
        CreateWindowW(L"BUTTON", L"Ligar", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 40, 250, 320, 52, hwnd, (HMENU)1, NULL, NULL);
        CreateWindowW(L"BUTTON", L"Desligar", WS_CHILD | WS_VISIBLE | BS_PUSHBUTTON, 40, 314, 320, 52, hwnd, (HMENU)2, NULL, NULL);
        g_status = CreateWindowW(L"STATIC", L"Pode ligar.", WS_CHILD | WS_VISIBLE | SS_CENTER, 20, 380, 360, 44, hwnd, NULL, NULL, NULL);
        PostMessageW(hwnd, WM_APP, 0, 0);
        return 0;
    }
    case WM_APP:
        ligar();
        return 0;
    case WM_COMMAND:
        if (LOWORD(wparam) == 1) ligar();
        if (LOWORD(wparam) == 2) desligar();
        return 0;
    case WM_PAINT: {
        PAINTSTRUCT pintura;
        HDC dc = BeginPaint(hwnd, &pintura);
        if (g_logo) {
            HDC mem = CreateCompatibleDC(dc);
            HBITMAP antigo = (HBITMAP)SelectObject(mem, g_logo);
            BITMAP info;
            GetObject(g_logo, sizeof info, &info);
            SetStretchBltMode(dc, HALFTONE);
            StretchBlt(dc, 70, 16, 260, 210, mem, 0, 0, info.bmWidth, info.bmHeight, SRCCOPY);
            SelectObject(mem, antigo);
            DeleteDC(mem);
        }
        EndPaint(hwnd, &pintura);
        return 0;
    }
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wparam, lparam);
}

int WINAPI wWinMain(HINSTANCE instancia, HINSTANCE, PWSTR, int mostrar) {
    WSADATA rede;
    WNDCLASSW classe;
    achar_raiz();
    caminho_python();
    WSAStartup(MAKEWORD(2, 2), &rede);
    ZeroMemory(&classe, sizeof classe);
    classe.lpfnWndProc = janela;
    classe.hInstance = instancia;
    classe.hCursor = LoadCursor(NULL, IDC_ARROW);
    classe.hbrBackground = (HBRUSH)(COLOR_WINDOW + 1);
    classe.lpszClassName = L"CaminhoDosDoces";
    classe.hIcon = LoadIconW(instancia, MAKEINTRESOURCEW(1));
    RegisterClassW(&classe);
    HWND hwnd = CreateWindowW(L"CaminhoDosDoces", L"Caminho dos Doces", WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX,
        CW_USEDEFAULT, CW_USEDEFAULT, 420, 480, NULL, NULL, instancia, NULL);
    SendMessageW(hwnd, WM_SETICON, ICON_BIG, (LPARAM)classe.hIcon);
    ShowWindow(hwnd, mostrar);
    UpdateWindow(hwnd);
    MSG msg;
    while (GetMessageW(&msg, NULL, 0, 0)) {
        TranslateMessage(&msg);
        DispatchMessageW(&msg);
    }
    WSACleanup();
    return 0;
}
