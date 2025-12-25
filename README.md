# Sistema de Análise Baccarat (SISTEMABACBO)

Descrição breve: protótipo profissional em Flask com login/cadastro, painel para inserir sequências da mesa e módulo de análise que detecta padrões (repetição, alternância) e fornece recomendação (Banker/Player/Tie) com score de confiança.

Como rodar (Windows Powershell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Observação: A precisão não pode ser garantida em 99%; o sistema fornece heurísticas e sinais de manipulação, use com responsabilidade.

Compatibilidade Python / Nota técnica:
- Em algumas versões mais novas do Python a API interna usada por frameworks pode não expor `pkgutil.get_loader`. Para compatibilidade rápida o arquivo `app.py` inclui um "shim" defensivo que fornece um fallback para `pkgutil.get_loader` quando necessário. Isso evita erros de inicialização em ambientes com `__main__.__spec__ is None`.
- Recomenda-se manter o projeto executando dentro de um virtualenv e usar a versão do Python do ambiente. Se preferir remover o shim, verifique se sua instalação do Python expõe `pkgutil.get_loader` e que não há módulos locais chamados `pkgutil.py` conflitando com a stdlib.
