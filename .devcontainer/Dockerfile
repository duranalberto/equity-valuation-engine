FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

USER vscode
WORKDIR /workspace

# Install Powerlevel10k and ZSH Plugins
RUN git clone --depth=1 https://github.com/romkatv/powerlevel10k.git ~/.oh-my-zsh/custom/themes/powerlevel10k \
    && git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions \
    && git clone https://github.com/zsh-users/zsh-syntax-highlighting.git ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting

# Setup ZSH configuration
RUN echo 'export ZSH="$HOME/.oh-my-zsh"' > ~/.zshrc \
    && echo 'ZSH_THEME="powerlevel10k/powerlevel10k"' >> ~/.zshrc \
    && echo 'plugins=(git zsh-autosuggestions zsh-syntax-highlighting)' >> ~/.zshrc \
    && echo 'source $ZSH/oh-my-zsh.sh' >> ~/.zshrc \
    && echo 'POWERLEVEL9K_LEFT_PROMPT_ELEMENTS=(dir vcs)' >> ~/.zshrc \
    && echo 'POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS=()' >> ~/.zshrc \
    && echo 'POWERLEVEL9K_SHORTEN_STRATEGY="truncate_to_first_and_last"' >> ~/.zshrc \
    && echo 'POWERLEVEL9K_MODE="nerdfont-complete"' >> ~/.zshrc \
    && echo '[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh' >> ~/.zshrc

ENV SHELL /bin/zsh