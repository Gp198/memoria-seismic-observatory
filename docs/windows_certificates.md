# Certificados HTTPS em Windows e redes empresariais

## Sintoma

```text
SSLCertVerificationError:
certificate verify failed: self-signed certificate in certificate chain
```

Quando o mesmo erro surge em vários domínios HTTPS, a causa mais provável é
inspeção TLS por proxy, VPN, firewall ou antivírus. O intermediário apresenta
um certificado assinado por uma autoridade interna que normalmente está
instalada no repositório de certificados do Windows.

## Solução implementada

O MEMÓRIA usa `truststore` para integrar o repositório nativo do sistema
operativo com Python e Requests.

Atualize a instalação:

```cmd
.venv\Scripts\activate
python -m pip install --upgrade -e .
```

Teste:

```cmd
python -m src.pipeline tls-diagnostics
python -m src.pipeline ingest-ipma --ipma-areas 7
python -m src.pipeline ingest-ahead
```

## Certificado empresarial fornecido em ficheiro

Caso a equipa de segurança forneça uma cadeia CA em formato PEM:

```cmd
set MEMORIA_CA_BUNDLE=C:\certificados\empresa-ca-chain.pem
python -m src.pipeline ingest-ipma --ipma-areas 7
```

Para tornar a definição persistente no Windows:

```cmd
setx MEMORIA_CA_BUNDLE "C:\certificados\empresa-ca-chain.pem"
```

Feche e volte a abrir a Linha de Comandos depois de executar `setx`.

Também é suportada a variável padrão:

```cmd
set REQUESTS_CA_BUNDLE=C:\certificados\empresa-ca-chain.pem
```

## Verificação rápida do Windows trust store

Depois de instalar a atualização:

```cmd
python -c "import truststore; truststore.inject_into_ssl(); import requests; print(requests.get('https://api.ipma.pt/open-data/observation/seismic/7.json', timeout=30).status_code)"
```

O resultado esperado é `200`.

## Não recomendado

Não altere permanentemente o código para:

```python
requests.get(url, verify=False)
```

Isto elimina a verificação da identidade do servidor e torna a ingestão
vulnerável a interceção. O projeto admite `MEMORIA_SSL_VERIFY=false` apenas
para diagnóstico temporário e emite um aviso explícito.
