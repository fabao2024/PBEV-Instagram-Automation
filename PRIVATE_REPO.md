# Private Repo Bootstrap

Este projeto esta pronto para virar um repositorio privado, mas o push inicial deve ser feito com alguns cuidados.

## O que pode ir para o repo privado

- codigo-fonte do bot
- docs operacionais
- `.env.example`
- configs de `systemd` e Nginx como referencia
- scripts de setup, deploy e diagnostico

## O que nao deve ir para git

- `.env`
- `pbev_instagram.db`
- tokens Meta, Gemini e Plausible
- chaves SSH, `.pem`, `.key`, `.crt`
- imagens geradas em `generated_images/`
- caches e artefatos locais

## Verificacao rapida antes do primeiro commit

No diretorio do projeto:

```bash
git status --ignored
```

Confirme que estes itens aparecem como ignorados:

- `.env`
- `pbev_instagram.db`
- `generated_images/`

## Importante sobre este diretorio

Hoje este projeto aparenta estar dentro de um repositorio maior. Antes de criar o repo privado dele, confira o topo do git atual:

```bash
git rev-parse --show-toplevel
```

Se o resultado for um diretorio acima deste projeto, faca um repositorio separado so para esta pasta.

## Criando um repo privado standalone

No PowerShell, dentro desta pasta:

```powershell
git init
git branch -M main
git add .
git commit -m "Initial private repo bootstrap"
```

Depois de criar o repo privado no GitHub:

```powershell
git remote add origin git@github.com:SEU_USUARIO/SEU_REPO_PRIVADO.git
git push -u origin main
```

## Recomendacao de acesso

Prefira remoto SSH, nao HTTPS com senha.

Exemplo:

```powershell
git remote set-url origin git@github.com:SEU_USUARIO/SEU_REPO_PRIVADO.git
```

## Estrategia recomendada

Use dois repositorios:

1. privado: operacao real, integrações, deploy e manutencao
2. publico: showcase sanitizado para portfolio

O repo publico deve ser derivado do privado, e nao o contrario.

## Checklist do repo privado

- `.gitignore` revisado
- `.env` fora do git
- banco SQLite fora do git
- docs atualizadas
- token real nunca copiado para README, QUICKSTART ou scripts
- push inicial feito para repo GitHub privado
