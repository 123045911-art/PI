const fs = require('fs');
const path = require('path');
const ngrok = require('@expo/ngrok');

const outputPath = path.resolve(__dirname, '..', '.api-tunnel-url');

function configuredAuthtoken() {
  const yaml = require('yaml');
  const candidates = [
    path.join(process.env.LOCALAPPDATA || '', 'ngrok', 'ngrok.yml'),
    path.join(process.env.USERPROFILE || '', '.ngrok2', 'ngrok.yml'),
  ];
  for (const configPath of candidates) {
    if (!configPath || !fs.existsSync(configPath)) continue;
    try {
      const config = yaml.parse(fs.readFileSync(configPath, 'utf8')) || {};
      const token = config.authtoken || config.agent?.authtoken;
      if (token) return token;
    } catch { /* probar la siguiente ubicación */ }
  }
  return undefined;
}

async function stop(exitCode = 0) {
  try { await ngrok.kill(); } catch { /* el proceso ya estaba cerrado */ }
  process.exit(exitCode);
}

async function main() {
  const authtoken = configuredAuthtoken();
  const publicUrl = await ngrok.connect({
    proto: 'http', addr: 8000, bind_tls: true, ...(authtoken ? { authtoken } : {}),
  });
  const httpsUrl = publicUrl.replace(/^http:/, 'https:');
  fs.writeFileSync(outputPath, httpsUrl, 'utf8');
  console.log('==============================================');
  console.log(' API FASTAPI PUBLICA');
  console.log(` ${httpsUrl}`);
  console.log(' Deja esta terminal abierta.');
  console.log('==============================================');
  setInterval(() => {}, 60_000);
}

process.on('SIGINT', () => void stop(0));
process.on('SIGTERM', () => void stop(0));
main().catch((error) => {
  console.error('[ERROR] No fue posible publicar FastAPI:', error.message);
  void stop(1);
});
