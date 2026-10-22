$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class QwenForCodexCredential
{
    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct CREDENTIAL
    {
        public uint Flags;
        public uint Type;
        public string TargetName;
        public string Comment;
        public long LastWritten;
        public uint CredentialBlobSize;
        public IntPtr CredentialBlob;
        public uint Persist;
        public uint AttributeCount;
        public IntPtr Attributes;
        public string TargetAlias;
        public string UserName;
    }

    [DllImport("advapi32.dll", EntryPoint = "CredReadW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool CredRead(string target, uint type, int reservedFlag, out IntPtr credentialPtr);

    [DllImport("advapi32.dll", SetLastError = true)]
    private static extern void CredFree(IntPtr credentialPtr);

    public static string Read(string target)
    {
        IntPtr pointer;
        if (!CredRead(target, 1, 0, out pointer))
        {
            throw new InvalidOperationException("未找到阿里云百炼 API Key，请重新运行 Qwen for Codex 设置。");
        }
        try
        {
            CREDENTIAL credential = Marshal.PtrToStructure<CREDENTIAL>(pointer);
            return Marshal.PtrToStringUni(
                credential.CredentialBlob,
                checked((int)credential.CredentialBlobSize / 2)
            );
        }
        finally
        {
            CredFree(pointer);
        }
    }
}
"@

try {
    $value = [QwenForCodexCredential]::Read("QwenForCodex:DashScopeAPIKey")
    [Console]::Out.Write($value)
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
