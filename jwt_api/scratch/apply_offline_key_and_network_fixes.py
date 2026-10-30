import os

# 1. Properly write db.ts with real PEM strings
WAREHOUSE_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhccR3oGXwI+jx4jhJuOY
Nv2xVrFCqhb11hYVHKh/lmrnIXtOldIdMtd2d9D3y5OT8+YnlSkfiT2EeMvtyoM3
aJGQpSBRGzwmn+1SZtUCeoZZ5SRHSBYpx9QhVAx20cP9Y1WWe5A3ppHyN9QMsxKk
ZRRlm7/husvcd+cjLwwqkJm+SDOxj9qVQV92pNMu8dZpLYVmJBSRVXPv9yO2CG+z
ISBKQG4scrZW6OObExu8UDRqR+PNc/2VyXgwl0YPGmRK/1HdQZKg2u5DJhmg91Fa
4Ia7w6jg45BfX9YuXecYMDZZmY5OdSu6fpFZ+4h4Szovxj93CqSmD9GQhwV5dMYP
6QIDAQAB
-----END PUBLIC KEY-----"""

LOGIN_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAqcx6Pu1PrcwkWHYwGtTg
YVwtc4Hfqr8DSlXWWj2MZcg9jVjhTDZEp3HycAoqSjDSCeyvHa1InXNl3i18DjyC
4R9lCdGmjHOdnWiwnE1dN+F6QXapMJqKPTuV2MYmDD5FNPyjCzR6PpsXnVoXEMpL
0kmQ7YJFkKI2V0vECE0X49KdEp21yMAR7lPQB/YdkgaM6w3p9+S+Dvc+QmMRvETT
kWRntq2TK5K1WbE8CYUiEiij+qzzrGSV7M9RsUgv2JRzssNDxIxwGycrd0AAjJla
vbyhm6gVayfY/CINobkgTV6YtwbHlzXY6uoKlSDcT/Cz0UFdDws8vMbP/XfwoFcb
xQIDAQAB
-----END PUBLIC KEY-----"""

db_path = '../app/veriflow/src/core/db.ts'
with open(db_path, 'r') as f:
    db_text = f.read()

bundled_block = f"""export const BUNDLED_DEFAULT_PUBLIC_KEYS: Array<{{ name: string; public_key_string: string }}> = [
  {{
    name: 'wearhouse101',
    public_key_string: `{WAREHOUSE_PEM}`,
  }},
  {{
    name: 'login123',
    public_key_string: `{LOGIN_PEM}`,
  }},
];
"""

# Replace the broken BUNDLED_DEFAULT_PUBLIC_KEYS block in db.ts
import re
db_text = re.sub(r'export const BUNDLED_DEFAULT_PUBLIC_KEYS[\s\S]*?;\n\n', '', db_text)
db_text = bundled_block + '\n' + db_text

with open(db_path, 'w') as f:
    f.write(db_text)

print('db.ts written successfully!')

# 2. Update LoginPage.tsx
login_path = '../app/veriflow/src/Pages/LoginPage.tsx'
with open(login_path, 'r') as f:
    login_text = f.read()

# Update handleFetchServerKeys to accept optional targetUrlOverride, normalize url, timeout 8s, and descriptive alerts
old_fetch_fn = re.search(r'  const handleFetchServerKeys = async \(silent: boolean = false\): Promise<PublicKeyRecord\[\]> => \{[\s\S]*?  \};', login_text)
if old_fetch_fn:
    new_fetch_fn = """  const handleFetchServerKeys = async (
    silent: boolean = false,
    targetUrlOverride?: string,
  ): Promise<PublicKeyRecord[]> => {
    setIsFetchingServerKeys(true);
    let targetBase = (targetUrlOverride || apiBaseUrl).trim().replace(/\\/+$/, '');
    if (!targetBase.startsWith('http://') && !targetBase.startsWith('https://')) {
      targetBase = `http://${targetBase}`;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);

      let res: Response | null = null;
      let networkError: string | null = null;

      try {
        res = await fetch(`${targetBase}/app/v1/keys/jwks`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
      } catch (err: any) {
        networkError = err.name === 'AbortError' ? 'Connection timed out after 8s' : (err.message || 'Network request failed');
      } finally {
        clearTimeout(timeoutId);
      }

      if (res && res.ok) {
        const jwks = await res.json();
        const keys = jwks.keys || [];
        if (keys.length === 0) {
          if (!silent) {
            Alert.alert('No Keys Found', 'Server returned 0 active keys in JWKS.');
          }
        } else {
          let addedCount = 0;
          for (const k of keys) {
            const pem =
              k.public_key ||
              (k.x5c && k.x5c[0]
                ? `-----BEGIN PUBLIC KEY-----\\n${k.x5c[0]}\\n-----END PUBLIC KEY-----`
                : null);

            if (pem) {
              const keyAlias = `Server Key ${k.kid || k.id || ''}`;
              await addPublicKey(keyAlias, pem);
              addedCount++;
            }
          }
          const updated = await loadKeys();
          if (updated.length > 0 && !selectedKeyId) {
            setSelectedKeyId(updated[0].id);
          }
          if (!silent) {
            Alert.alert('Keys Updated', `Successfully fetched and synced ${addedCount} public key(s) from server.`);
          }
          return updated;
        }
      } else {
        if (!silent) {
          Alert.alert(
            'Connection Failed',
            `Could not reach ${targetBase}/app/v1/keys/jwks.\\n\\nDiagnostic: ${networkError || ('HTTP ' + (res?.status || 'Unknown'))}\\n\\nTroubleshooting Tips:\\n1. Ensure Android device & PC are on the same Wi-Fi network.\\n2. Verify the IP address (e.g. http://192.168.100.185:8000).\\n3. Ensure your PC firewall allows incoming connections on port 8000.`,
          );
        }
      }
    } catch (e: any) {
      if (!silent) {
        Alert.alert('Error', e.message || 'Failed connecting to server');
      }
    } finally {
      setIsFetchingServerKeys(false);
    }
    return publicKeys;
  };"""
    login_text = login_text.replace(old_fetch_fn.group(0), new_fetch_fn)

# In serverModal Save & Refetch, pass sanitized serverUrlInput directly
old_save_btn = re.search(r'onPress=\{async \(\) => \{\s*await setApiBaseUrl\(serverUrlInput\);\s*setServerModalVisible\(false\);\s*await handleFetchServerKeys\(false\);\s*\}\}', login_text)
if old_save_btn:
    new_save_btn = """onPress={async () => {
                  let sanitized = serverUrlInput.trim().replace(/\\/+$/, '');
                  if (!sanitized.startsWith('http://') && !sanitized.startsWith('https://')) {
                    sanitized = `http://${sanitized}`;
                  }
                  setServerUrlInput(sanitized);
                  await setApiBaseUrl(sanitized);
                  setServerModalVisible(false);
                  await handleFetchServerKeys(false, sanitized);
                }}"""
    login_text = login_text.replace(old_save_btn.group(0), new_save_btn)

with open(login_path, 'w') as f:
    f.write(login_text)

print('LoginPage.tsx updated successfully!')

# 3. Update SettingsPage.tsx
settings_path = '../app/veriflow/src/Pages/SettingsPage.tsx'
with open(settings_path, 'r') as f:
    settings_text = f.read()

old_settings_fetch = re.search(r'  const fetchServerKeys = async \(\) => \{[\s\S]*?  \};', settings_text)
if old_settings_fetch:
    new_settings_fetch = """  const fetchServerKeys = async () => {
    if (!canCreateKeys) {
      Alert.alert('Permission Denied', 'Importing keys requires "keys.create" permission.');
      return;
    }

    setIsFetchingServerKeys(true);
    let targetBase = apiBaseUrl.trim().replace(/\\/+$/, '');
    if (!targetBase.startsWith('http://') && !targetBase.startsWith('https://')) {
      targetBase = `http://${targetBase}`;
    }

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);

      let res: Response | null = null;
      let networkError: string | null = null;

      try {
        res = await fetch(`${targetBase}/app/v1/keys/jwks`, {
          headers: { Accept: 'application/json' },
          signal: controller.signal,
        });
      } catch (err: any) {
        networkError = err.name === 'AbortError' ? 'Connection timed out after 8s' : (err.message || 'Network request failed');
      } finally {
        clearTimeout(timeoutId);
      }

      if (res && res.ok) {
        const jwks = await res.json();
        const keys = jwks.keys || [];
        if (keys.length === 0) {
          Alert.alert('No Keys Found', 'Server returned 0 active keys in JWKS.');
        } else {
          let addedCount = 0;
          for (const k of keys) {
            const pem =
              k.public_key ||
              (k.x5c && k.x5c[0]
                ? `-----BEGIN PUBLIC KEY-----\\n${k.x5c[0]}\\n-----END PUBLIC KEY-----`
                : null);

            if (pem) {
              const keyAlias = `Server Key ${k.kid || k.id || ''}`;
              await addPublicKey(keyAlias, pem);
              addedCount++;
            }
          }
          await refresh();
          Alert.alert('Import Complete', `Successfully imported ${addedCount} public key(s) from server.`);
        }
      } else {
        Alert.alert(
          'Connection Failed',
          `Could not reach ${targetBase}/app/v1/keys/jwks.\\n\\nDiagnostic: ${networkError || ('HTTP ' + (res?.status || 'Unknown'))}\\n\\nTroubleshooting Tips:\\n1. Ensure Android device & PC are on the same Wi-Fi network.\\n2. Verify the IP address (e.g. http://192.168.100.185:8000).\\n3. Ensure your PC firewall allows incoming connections on port 8000.`,
        );
      }
    } catch (err: any) {
      Alert.alert('Fetch Error', err.message || 'Could not fetch public keys from server.');
    } finally {
      setIsFetchingServerKeys(false);
    }
  };"""
    settings_text = settings_text.replace(old_settings_fetch.group(0), new_settings_fetch)

with open(settings_path, 'w') as f:
    f.write(settings_text)

print('SettingsPage.tsx updated successfully!')
