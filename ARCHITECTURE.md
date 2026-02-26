# Arquitetura Simplificada

## Camadas

1. **Domain** (`src/callisto/domain/`): Modelos Pydantic que representam as entidades centrais do domínio (Buffer, Config, Firmware, OVSItem, ScheduleEntry).
2. **Application** (`src/callisto/application/`): Casos de uso e orquestração — carregamento de configuração, tabela de frequências, processamento de comandos TCP.
3. **Infrastructure** (`src/callisto/infrastructure/`): Tudo externo ao domínio — backend serial assíncrono, escritores FITS/HDF5, publicador ZeroMQ, e as interfaces (portas) que definem os contratos entre camadas.
4. **API** (`src/callisto/api/`): Interface HTTP/REST (reservado para uso futuro).

## Estrutura de Diretórios

```
callisto/
├── src/callisto/           # Pacote principal
│   ├── domain/            # Modelos de domínio (Pydantic)
│   ├── application/       # Casos de uso e regras de negócio
│   ├── infrastructure/    # Tudo externo: serial, arquivos, ZeroMQ
│   │   └── ports.py      # Interfaces (contratos) da camada hexagonal
│   └── api/              # Interfaces HTTP/REST (futuro)
├── tests/                # Testes organizados por camada
│   ├── unit/
│   │   ├── application/  # Testes de casos de uso
│   │   ├── domain/       # Testes de modelos
│   │   └── infrastructure/ # Testes de adaptadores
│   ├── integration/      # Testes de integração
│   └── conftest.py       # Fixtures compartilhadas
├── config/               # Configuração unificada
│   ├── settings.py       # Pydantic Settings centralizado
│   ├── callisto.cfg      # Configuração do receptor e-Callisto
│   └── scheduler.cfg     # Configuração do agendador
├── examples/             # Arquivos de frequência de exemplo
│   ├── frq00005.cfg
│   └── frq00400.cfg
├── docs/                 # Documentação Sphinx
└── notebooks/            # Notebooks científicos (futuro)
```

## Princípios

- **Dependency Inversion**: Camadas superiores dependem de abstrações (portas), não de implementações concretas.
- **Single Responsibility**: Cada classe ou módulo tem uma razão única para mudar.
- **Explicit is better than implicit**: Type hints em todas as funções e métodos públicos.
- **Hexagonal Architecture**: O domínio e a aplicação são independentes de frameworks externos.

## Fluxo de Dependências

```
API / CLI
    ↓
Application (casos de uso)
    ↓
Domain (modelos)
    ↑
Infrastructure (adaptadores implementam as portas do domain/application)
```

## Compatibilidade

Os módulos de fachada no nível do pacote (`callisto/serial_backend.py`, `callisto/writers.py`, `callisto/zmq_pub.py`, `callisto/control.py`) mantêm a API pública estável para código existente enquanto delegam para as implementações em `callisto.infrastructure`.
