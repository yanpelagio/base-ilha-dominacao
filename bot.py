# bot.py
import os
import sqlite3
import discord
from discord import app_commands, ui, Interaction, Embed, Colour
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
import traceback
from config import (
    GUILD_ID,
    CANAL_VENDAS_ID,
    EMBED_TITLE,
    EMBED_DESCRIPTION,
    TOTAL_BASES,
    CARGO_ADM_ID,
)

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -------------------------------------------------
#  Banco de Dados SQLite
# -------------------------------------------------
def init_database():
    """Inicializa o banco de dados."""
    conn = sqlite3.connect('bases.db')
    cursor = conn.cursor()
    
    # Tabela para as bases
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bases (
        numero INTEGER PRIMARY KEY,
        nome TEXT,
        data TEXT,
        responsavel TEXT,
        status TEXT DEFAULT 'livre',
        data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Tabela para histórico
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS historico (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        base_numero INTEGER,
        status TEXT,
        nome TEXT,
        data TEXT,
        responsavel TEXT,
        motivo TEXT,
        data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (base_numero) REFERENCES bases(numero)
    )
    ''')
    
    # Insere as bases padrão se não existirem
    for i in range(1, TOTAL_BASES + 1):
        cursor.execute('''
        INSERT OR IGNORE INTO bases (numero) VALUES (?)
        ''', (i,))
    
    conn.commit()
    conn.close()

def carregar_bases_do_banco():
    """Carrega as bases do banco de dados."""
    conn = sqlite3.connect('bases.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM bases ORDER BY numero')
    bases_data = cursor.fetchall()
    
    # Reconstrói a lista de objetos Base
    bases_atuais = []
    for base_data in bases_data:
        base = Base(base_data[0])  # numero
        base.nome = base_data[1]   # nome
        base.data = base_data[2]   # data
        base.responsavel = base_data[3]  # responsavel
        base.status = base_data[4]  # status
        
        # Carrega histórico
        cursor.execute('''
        SELECT status, nome, data, responsavel, motivo, data_registro 
        FROM historico 
        WHERE base_numero = ? 
        ORDER BY data_registro DESC
        ''', (base.numero,))
        
        historico_data = cursor.fetchall()
        base.historico = []
        for registro in historico_data:
            base.historico.append({
                'status': registro[0],
                'nome': registro[1],
                'data': registro[2],
                'responsavel': registro[3],
                'motivo': registro[4],
                'data_registro': registro[5]
            })
        
        bases_atuais.append(base)
    
    conn.close()
    return bases_atuais

def salvar_base(base):
    """Salva uma base no banco de dados."""
    conn = sqlite3.connect('bases.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    UPDATE bases 
    SET nome = ?, data = ?, responsavel = ?, status = ?, data_atualizacao = CURRENT_TIMESTAMP
    WHERE numero = ?
    ''', (base.nome, base.data, base.responsavel, base.status, base.numero))
    
    conn.commit()
    conn.close()

def adicionar_historico(base, status, nome=None, data=None, responsavel=None, motivo=None):
    """Adiciona um registro ao histórico no banco de dados."""
    conn = sqlite3.connect('bases.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT INTO historico (base_numero, status, nome, data, responsavel, motivo)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (base.numero, status, nome, data, responsavel, motivo))
    
    conn.commit()
    conn.close()

# Inicializa o banco de dados
init_database()

# -------------------------------------------------
#  Estrutura de dados das bases com coordenadas fixas
# -------------------------------------------------
class Base:
    def __init__(self, numero: int):
        self.numero = numero
        self.cds = self.get_coordenadas_fixas()  # Coordenadas fixas para cada base
        self.nome = None
        self.data = None
        self.responsavel = None
        self.status = "livre"  # livre | reservada | ocupada
        self.foto_path = f"fotos-base/base {self.numero}.png"
        self.historico = []
    
    def get_coordenadas_fixas(self):
        """Retorna as coordenadas fixas para cada base."""
        coordenadas = {
            1: "4767.86, -6014.95, 31.93",
            2: "4733.57, -5608.5, 35.08",
            3: "4818.07, -5280.29, 22.43",
            4: "4854.77, -4929.04, 15.08",
            5: "5526.66, -5874.5, 36.75",
            6: "4671.42, -4648.25, 17.98",
            7: "4142.85, -4465.0, 14.14",
            8: "5579.31, -5169.58, 26.44",
            9: "4835.74, -4279.06, 17.09",
            10: "5045.78, -4458.42, 15.13",
            11: "5385.28, -5088.19, 26.67",
            12: "5196.73, -4696.33, 14.05",
            13: "5144.96, -4839.99, 19.12",
            14: "5095.63, -5055.89, 14.52"
        }
        return coordenadas.get(self.numero, "Coordenadas não definidas")
    
    def info_detalhada(self, mostrar_cds: bool = False, mostrar_nome: bool = True) -> str:
        """Retorna informações detalhadas da base."""
        status_emoji = "🟢" if self.status == "livre" else "🔴" if self.status == "ocupada" else "🟡"
        info = f"{status_emoji} **Base {self.numero}** - {self.status.title()}\n"
        
        if mostrar_cds:  # Apenas para ADM
            info += f"**Coordenadas:** {self.cds}\n"
        
        if mostrar_nome and self.nome:
            info += f"**Facção:** {self.nome}\n"
        
        if self.data:
            info += f"**Data/Hora:** {self.data}\n"
        
        if self.responsavel and self.status in ["ocupada", "reservada"] and mostrar_nome:
            info += f"**Responsável:** {self.responsavel}\n"
        
        # Adiciona histórico recente se houver
        if self.historico and mostrar_nome:  # Histórico apenas para ADM
            ultimo = self.historico[0]  # Mais recente
            info += f"\n**Última alteração:**\n"
            info += f"Data: {ultimo['data_registro']}\n"
            if ultimo['responsavel']:
                info += f"Responsável: {ultimo['responsavel']}\n"
            if ultimo['motivo']:
                info += f"Motivo: {ultimo['motivo']}"
        
        return info
    
    def info_simples(self, mostrar_nome: bool = False) -> str:
        """Retorna informações simples da base (apenas status)."""
        status_emoji = "🟢" if self.status == "livre" else "🔴" if self.status == "ocupada" else "🟡"
        info = f"{status_emoji} **Base {self.numero}** - {self.status.title()}"
        
        if mostrar_nome and self.nome:
            info += f" ({self.nome})"
        
        return info

# Carrega as bases do banco de dados
bases = carregar_bases_do_banco()

# -------------------------------------------------
#  Funções auxiliares
# -------------------------------------------------
def atualizar_painel_principal():
    """Atualiza o painel principal no canal de vendas."""
    channel = bot.get_channel(CANAL_VENDAS_ID)
    if channel:
        async def encontrar_e_atualizar():
            async for msg in channel.history(limit=200):
                if msg.author == bot.user and msg.embeds:
                    embed = get_embed_main()
                    await msg.edit(embed=embed, view=MainView())
                    return True
            return False
        
        import asyncio
        asyncio.create_task(encontrar_e_atualizar())

def get_embed_main() -> Embed:
    """Embed principal que será enviado no canal de vendas."""
    embed = Embed(
        title=EMBED_TITLE,
        description=EMBED_DESCRIPTION,
        colour=Colour.gold(),
    )
    
    livres = sum(1 for b in bases if b.status == "livre")
    reservadas = sum(1 for b in bases if b.status == "reservada")
    ocupadas = sum(1 for b in bases if b.status == "ocupada")
    
    embed.add_field(
        name="📊 Status das Bases",
        value=(
            f"🟢 **{livres}** Bases Livres\n"
            f"🟡 **{reservadas}** Bases Reservadas\n"
            f"🔴 **{ocupadas}** Bases Ocupadas\n"
            f"📦 **Total:** {TOTAL_BASES} Bases"
        ),
        inline=False
    )
    
    return embed

def listar_bases_simples(mostrar_nome: bool = False) -> str:
    """Retorna uma string formatada com todas as bases (apenas status)."""
    lista = ""
    for b in bases:
        lista += b.info_simples(mostrar_nome=mostrar_nome) + "\n"
    return lista or "Nenhuma base encontrada."

def listar_bases_completo(mostrar_cds: bool = False, mostrar_nome: bool = True) -> str:
    """Retorna uma string formatada com todas as bases e suas informações (apenas ADM)."""
    lista = ""
    for b in bases:
        if b.status == "livre":
            lista += "🟢 "
        elif b.status == "ocupada":
            lista += "🔴 "
        elif b.status == "reservada":
            lista += "🟡 "
            
        lista += f"**Base {b.numero}** - {b.status.title()}\n"
        
        if mostrar_cds:  # Apenas para ADM
            lista += f"   📍 **Coordenadas:** {b.cds}\n"
        
        if mostrar_nome and b.nome:
            lista += f"   📛 **Facção:** {b.nome}\n"
        
        if b.data:
            lista += f"   📅 **Data/Hora:** {b.data}\n"
        
        if b.responsavel and b.status in ["ocupada", "reservada"] and mostrar_nome:
            lista += f"   👤 **Responsável:** {b.responsavel}\n"
        
        lista += "\n"
    return lista or "Nenhuma base encontrada."

def listar_bases(filtro: str = None, mostrar_cds: bool = False, mostrar_nome: bool = True) -> str:
    """Retorna uma string formatada com as bases filtradas."""
    lista = ""
    for b in bases:
        if filtro and b.status != filtro:
            continue
        
        if b.status == "livre":
            lista += "🟢 "
        elif b.status == "ocupada":
            lista += "🔴 "
        elif b.status == "reservada":
            lista += "🟡 "
            
        lista += f"**Base {b.numero}**"
        
        if mostrar_nome and b.nome:
            lista += f" - {b.nome}"
        
        lista += f" ({b.status.title()})\n"
        
        if mostrar_cds:  # Apenas para ADM
            lista += f"   📍 Coordenadas: {b.cds}\n"
    
    return lista or "Nenhuma base encontrada."

def get_base_info_embed(base_num: int, mostrar_cds: bool = False, mostrar_nome: bool = True) -> tuple:
    """Retorna um embed com informações detalhadas de uma base específica."""
    base = next((b for b in bases if b.numero == base_num), None)
    if not base:
        return Embed(title="Base não encontrada", colour=Colour.red()), None, False
    
    if base.status == "livre":
        colour = Colour.green()
        status_emoji = "🟢"
    elif base.status == "ocupada":
        colour = Colour.red()
        status_emoji = "🔴"
    elif base.status == "reservada":
        colour = Colour.orange()
        status_emoji = "🟡"
    else:
        colour = Colour.greyple()
        status_emoji = "⚪"
    
    embed = Embed(
        title=f"{status_emoji} Base {base.numero}",
        colour=colour,
    )
    
    # Adiciona a foto como attachment
    file = None
    foto_carregada = False
    try:
        if os.path.exists(base.foto_path):
            file = discord.File(base.foto_path, filename=f"base_{base.numero}.png")
            embed.set_image(url=f"attachment://base_{base.numero}.png")
            foto_carregada = True
        else:
            embed.add_field(name="⚠️ Aviso", value="Foto da base não encontrada.", inline=False)
    except Exception as e:
        print(f"Erro ao carregar foto da base {base.numero}: {e}")
        embed.add_field(name="⚠️ Aviso", value="Erro ao carregar foto da base.", inline=False)
    
    # Adiciona os campos de informação
    embed.add_field(name="Status", value=f"{status_emoji} {base.status.title()}", inline=True)
    
    if mostrar_cds:  # Apenas para ADM
        embed.add_field(name="Coordenadas", value=base.cds, inline=True)
    
    if mostrar_nome:
        embed.add_field(name="Facção", value=base.nome or "Não definida", inline=True)
    
    embed.add_field(name="Data/Hora", value=base.data or "Não definida", inline=True)
    
    if base.responsavel and base.status in ["ocupada", "reservada"] and mostrar_nome:
        embed.add_field(name="Responsável", value=base.responsavel, inline=True)
    
    # Adiciona histórico se houver e for ADM
    if base.historico and mostrar_nome:
        historico_text = ""
        for i, registro in enumerate(base.historico[:5], 1):  # 5 mais recentes
            status_emoji_hist = "🟢" if registro['status'] == "livre" else "🔴" if registro['status'] == "ocupada" else "🟡"
            data_formatada = registro['data_registro'].split('.')[0] if registro['data_registro'] else "Data desconhecida"
            historico_text += f"{i}. {status_emoji_hist} {registro['status'].title()} em {data_formatada}\n"
            if registro['nome']:
                historico_text += f"   Facção: {registro['nome']}\n"
            if registro['responsavel']:
                historico_text += f"   Responsável: {registro['responsavel']}\n"
            if registro['motivo']:
                historico_text += f"   Motivo: {registro['motivo']}\n"
            historico_text += "\n"
        
        if historico_text:
            embed.add_field(name="📜 Histórico Recente", value=historico_text[:1024], inline=False)
    
    return embed, file, foto_carregada

def has_admin_role(interaction: Interaction) -> bool:
    """Verifica se o usuário tem o cargo de administrador."""
    if not CARGO_ADM_ID:
        return interaction.user.guild_permissions.administrator
    
    admin_role = interaction.guild.get_role(CARGO_ADM_ID)
    if not admin_role:
        return interaction.user.guild_permissions.administrator
    
    return admin_role in interaction.user.roles

# -------------------------------------------------
#  Funções para criar embeds com fotos
# -------------------------------------------------
async def criar_embed_com_foto(base: Base, posicao: int, total: int, mostrar_cds: bool = False, mostrar_nome: bool = True):
    """Cria um embed com foto da base."""
    if base.status == "livre":
        colour = Colour.green()
        status_emoji = "🟢"
    elif base.status == "ocupada":
        colour = Colour.red()
        status_emoji = "🔴"
    elif base.status == "reservada":
        colour = Colour.orange()
        status_emoji = "🟡"
    else:
        colour = Colour.blue()
        status_emoji = "⚪"
    
    embed = Embed(title=f"📸 Base {base.numero} - {status_emoji} {base.status.title()}", colour=colour)
    
    # Adiciona informações da base
    info_text = f"**Status:** {status_emoji} {base.status.title()}\n"
    
    if mostrar_cds:  # Apenas para ADM
        info_text += f"**Coordenadas:** {base.cds}\n"
    
    if mostrar_nome and base.nome:
        info_text += f"**Facção:** {base.nome}\n"
    
    if base.data:
        info_text += f"**Data/Hora:** {base.data}\n"
    
    if base.responsavel and base.status in ["ocupada", "reservada"] and mostrar_nome:
        info_text += f"**Responsável:** {base.responsavel}\n"
    
    embed.description = info_text
    
    if mostrar_cds:  # Modo ADM
        embed.set_footer(text=f"Página {posicao}/{total} • Navegue usando as setas")
    else:
        embed.set_footer(text=f"Base {posicao}/{total} disponíveis • Navegue usando as setas")
    
    # Carrega a foto
    file = None
    if os.path.exists(base.foto_path):
        file = discord.File(base.foto_path, filename=f"base_{base.numero}.png")
        embed.set_image(url=f"attachment://base_{base.numero}.png")
    else:
        embed.add_field(name="⚠️ Aviso", value="Foto da base não encontrada.", inline=False)
    
    return embed, file

# -------------------------------------------------
#  Classes base melhoradas
# -------------------------------------------------
class SafeView(ui.View):
    """View base com tratamento seguro de interações."""
    
    async def on_error(self, interaction: Interaction, error: Exception, item: ui.Item):
        """Trata erros nas views."""
        if isinstance(error, discord.errors.NotFound):
            # Interação expirada, apenas ignore
            return
            
        print(f"Erro na view {self.__class__.__name__}: {error}")
        traceback.print_exc()
        
        # Tenta enviar mensagem de erro se possível
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Ocorreu um erro ao processar sua ação. Tente novamente.",
                    ephemeral=True
                )
            elif not interaction.is_expired():
                await interaction.followup.send(
                    "❌ Ocorreu um erro ao processar sua ação. Tente novamente.",
                    ephemeral=True
                )
        except:
            pass

# -------------------------------------------------
#  Views principais (com custom_id para persistência)
# -------------------------------------------------
class MainView(SafeView):
    """View com os dois botões do embed principal."""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔎VISUALIZAR BASES", style=discord.ButtonStyle.primary, custom_id="persistent:vis_bases")
    async def visualizar_bases(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            # Use defer para evitar timeouts
            await interaction.response.defer(ephemeral=True)
            
            view = MenuVisualizacaoView()
            await interaction.followup.send(
                embed=Embed(
                    title="📍 Visualização de Bases",
                    description="Escolha uma opção:",
                    colour=Colour.blurple(),
                ),
                view=view,
                ephemeral=True
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em visualizar_bases: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="👑MENU ADM", style=discord.ButtonStyle.success, custom_id="persistent:menu_adm")
    async def menu_adm(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            # Use defer para evitar timeouts
            await interaction.response.defer(ephemeral=True)
            
            if not has_admin_role(interaction):
                await interaction.followup.send(
                    f"❌ Você não tem permissão para acessar o menu administrativo.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}> para usar esta função.", 
                    ephemeral=True
                )
                return

            view = AdminMenuView()
            await interaction.followup.send(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                ephemeral=True
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em menu_adm: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


class MenuVisualizacaoView(SafeView):
    """View para o menu de visualização de bases."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📋 Ver Lista Completa", style=discord.ButtonStyle.primary, custom_id="vis:lista_completa")
    async def lista_completa(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            # Para usuários comuns, não mostra nomes
            mostrar_nome = has_admin_role(interaction)
            embed = Embed(
                title="📍 Todas as Bases",
                description=listar_bases_simples(mostrar_nome=mostrar_nome),
                colour=Colour.blurple(),
            )
            embed.set_footer(text="Use os botões abaixo para navegar")
            
            view = ListaCompletaView()
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em lista_completa: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="📸 Visualizar Fotos Disponíveis", style=discord.ButtonStyle.secondary, custom_id="vis:fotos_disponiveis")
    async def fotos_disponiveis(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            bases_disponiveis = [b for b in bases if b.status == "livre"]
            if not bases_disponiveis:
                await interaction.response.edit_message(
                    embed=Embed(
                        title="📸 Fotos das Bases Disponíveis",
                        description="❌ Não há bases disponíveis no momento.",
                        colour=Colour.red()
                    ),
                    view=self,
                    attachments=[]
                )
                return
            
            primeira_base = bases_disponiveis[0]
            # Para usuários comuns, não mostra nomes
            mostrar_nome = has_admin_role(interaction)
            embed, file = await criar_embed_com_foto(primeira_base, 1, len(bases_disponiveis), 
                                                    mostrar_cds=False, mostrar_nome=mostrar_nome)
            
            view = BasePhotosDisponiveisView(current_page=primeira_base.numero)
            
            if file:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em fotos_disponiveis: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="vis:voltar_menu")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            await interaction.response.edit_message(
                embed=Embed(
                    title="📍 Visualização de Bases",
                    description="Escolha uma opção:",
                    colour=Colour.blurple(),
                ),
                view=self,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


class ListaCompletaView(SafeView):
    """View para a lista completa de bases."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.primary, custom_id="lista:atualizar")
    async def atualizar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            # Para usuários comuns, não mostra nomes
            mostrar_nome = has_admin_role(interaction)
            embed = Embed(
                title="📍 Todas as Bases",
                description=listar_bases_simples(mostrar_nome=mostrar_nome),
                colour=Colour.blurple(),
            )
            embed.set_footer(text="Última atualização: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em atualizar lista: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="lista:voltar")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = MenuVisualizacaoView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="📍 Visualização de Bases",
                    description="Escolha uma opção:",
                    colour=Colour.blurple(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar lista: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


# -------------------------------------------------
#  Menu ADM (com custom_id) - ADICIONADO BASES RESERVADAS
# -------------------------------------------------
class AdminMenuView(SafeView):
    """View do menu ADM com opções administrativas."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="BASES DISPONÍVEIS", style=discord.ButtonStyle.success, custom_id="adm:bases_disponiveis")
    async def bases_disponiveis(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return
                
            embed = Embed(
                title="🟢 Bases Disponíveis",
                description=listar_bases(filtro="livre", mostrar_cds=True, mostrar_nome=True),
                colour=Colour.green(),
            )
            view = AdminBasesDisponiveisView()
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em bases_disponiveis: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="BASES RESERVADAS", style=discord.ButtonStyle.primary, custom_id="adm:bases_reservadas")  # NOVO BOTÃO
    async def bases_reservadas(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return
                
            embed = Embed(
                title="🟡 Bases Reservadas",
                description=listar_bases(filtro="reservada", mostrar_cds=True, mostrar_nome=True),
                colour=Colour.orange(),
            )
            view = AdminBasesReservadasView()
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em bases_reservadas: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="BASES OCUPADAS", style=discord.ButtonStyle.danger, custom_id="adm:bases_ocupadas")
    async def bases_ocupadas(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return
                
            embed = Embed(
                title="🔴 Bases Ocupadas",
                description=listar_bases(filtro="ocupada", mostrar_cds=True, mostrar_nome=True),
                colour=Colour.red(),
            )
            view = AdminBasesOcupadasView()
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em bases_ocupadas: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="📋 VISUALIZAR LISTA", style=discord.ButtonStyle.primary, custom_id="adm:visualizar_lista")
    async def visualizar_lista(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return
            
            embed = Embed(
                title="📊 Lista Completa de Bases (ADM)",
                description=listar_bases_completo(mostrar_cds=True, mostrar_nome=True),
                colour=Colour.purple(),
            )
            embed.set_footer(text="Apenas para administradores")
            
            view = AdminListaCompletaView()
            await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em visualizar_lista: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="📸 VER FOTOS TODAS AS BASES", style=discord.ButtonStyle.primary, custom_id="adm:fotos_todas")
    async def fotos_todas_bases(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return
            
            primeira_base = bases[0]
            embed, file = await criar_embed_com_foto(primeira_base, 1, TOTAL_BASES, 
                                                    mostrar_cds=True, mostrar_nome=True)
            
            view = AdminFotosTodasView(current_page=1)
            
            if file:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=view, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em fotos_todas_bases: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar ao Início", style=discord.ButtonStyle.secondary, custom_id="adm:voltar_inicio")
    async def voltar_inicio(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar_inicio: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


class AdminListaCompletaView(SafeView):
    """View para lista completa no menu ADM."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 Atualizar", style=discord.ButtonStyle.primary, custom_id="adm_lista:atualizar")
    async def atualizar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            embed = Embed(
                title="📊 Lista Completa de Bases (ADM)",
                description=listar_bases_completo(mostrar_cds=True, mostrar_nome=True),
                colour=Colour.purple(),
            )
            embed.set_footer(text="Última atualização: " + datetime.now().strftime("%d/%m/%Y %H:%M"))
            await interaction.response.edit_message(embed=embed, view=self, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em atualizar ADM: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="adm_lista:voltar")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar ADM: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


# -------------------------------------------------
#  Views de ações ADM - BASES DISPONÍVEIS
# -------------------------------------------------
class AdminBasesDisponiveisView(SafeView):
    """View para bases disponíveis no menu ADM."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="OCUPAR", style=discord.ButtonStyle.success, custom_id="adm_disp:ocupar")
    async def ocupar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return

            bases_livres = [b for b in bases if b.status == "livre"]
            if not bases_livres:
                await interaction.response.send_message(
                    "❌ Não há bases livres para ocupar.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(OcuparBaseModal())
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em ocupar: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="EM PROCESSO", style=discord.ButtonStyle.primary, custom_id="adm_disp:reservar")
    async def reservar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return

            bases_livres = [b for b in bases if b.status == "livre"]
            if not bases_livres:
                await interaction.response.send_message(
                    "❌ Não há bases livres para reservar.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(ReservarBaseModal())
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em reservar: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="adm_disp:voltar")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar disponiveis: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


# -------------------------------------------------
#  Views de ações ADM - BASES RESERVADAS (NOVO)
# -------------------------------------------------
class AdminBasesReservadasView(SafeView):
    """View para bases reservadas no menu ADM."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="OCUPAR", style=discord.ButtonStyle.success, custom_id="adm_res:ocupar")
    async def ocupar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return

            bases_reservadas = [b for b in bases if b.status == "reservada"]
            if not bases_reservadas:
                await interaction.response.send_message(
                    "❌ Não há bases reservadas para ocupar.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(OcuparBaseReservadaModal())
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em ocupar reservada: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="DISPONIBILIZAR", style=discord.ButtonStyle.danger, custom_id="adm_res:disponibilizar")
    async def disponibilizar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return

            bases_reservadas = [b for b in bases if b.status == "reservada"]
            if not bases_reservadas:
                await interaction.response.send_message(
                    "❌ Não há bases reservadas para disponibilizar.",
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(DisponibilizarBaseModal())
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em disponibilizar: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="adm_res:voltar")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar reservadas: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


# -------------------------------------------------
#  Views de ações ADM - BASES OCUPADAS
# -------------------------------------------------
class AdminBasesOcupadasView(SafeView):
    """View para bases ocupadas no menu ADM."""
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔄 DESOCUPAR BASE", style=discord.ButtonStyle.danger, custom_id="adm_ocup:desocupar")
    async def desocupar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not has_admin_role(interaction):
                await interaction.response.send_message(
                    f"❌ Você não tem permissão.\n"
                    f"É necessário ter o cargo <@&{CARGO_ADM_ID}>.", 
                    ephemeral=True
                )
                return

            await interaction.response.send_modal(DesocuparBaseModal())
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em desocupar: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass

    @ui.button(label="↩️ Voltar", style=discord.ButtonStyle.secondary, custom_id="adm_ocup:voltar")
    async def voltar(self, interaction: Interaction, button: ui.Button):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar ocupadas: {e}")
            traceback.print_exc()
            
            # Tenta enviar mensagem de erro
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ Ocorreu um erro. Tente novamente.",
                        ephemeral=True
                    )
            except:
                pass


# -------------------------------------------------
#  Views para fotos
# -------------------------------------------------
class BasePhotosDisponiveisView(SafeView):
    """View para navegar entre as fotos das bases disponíveis."""
    def __init__(self, current_page: int = 1):
        super().__init__(timeout=180)
        self.current_page = current_page
        
        # Encontra próxima base disponível
        bases_disponiveis = [b for b in bases if b.status == "livre"]
        self.numeros_disponiveis = [b.numero for b in bases_disponiveis]
        
        if self.current_page not in self.numeros_disponiveis:
            self.current_page = self.numeros_disponiveis[0] if self.numeros_disponiveis else 1
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        if not self.numeros_disponiveis:
            return
        
        current_idx = self.numeros_disponiveis.index(self.current_page) if self.current_page in self.numeros_disponiveis else 0
        
        # Botão Anterior
        prev_button = ui.Button(
            label="◀️ Anterior", 
            style=discord.ButtonStyle.primary,
            disabled=(current_idx == 0)
        )
        prev_button.callback = self.prev_page_callback
        self.add_item(prev_button)
        
        # Botão Próximo
        next_button = ui.Button(
            label="Próximo ▶️", 
            style=discord.ButtonStyle.primary,
            disabled=(current_idx == len(self.numeros_disponiveis) - 1)
        )
        next_button.callback = self.next_page_callback
        self.add_item(next_button)
        
        # Botão Voltar
        voltar_button = ui.Button(
            label="↩️ Voltar", 
            style=discord.ButtonStyle.secondary
        )
        voltar_button.callback = self.voltar_callback
        self.add_item(voltar_button)
    
    async def prev_page_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not self.numeros_disponiveis:
                return
            
            current_idx = self.numeros_disponiveis.index(self.current_page) if self.current_page in self.numeros_disponiveis else 0
            
            if current_idx > 0:
                self.current_page = self.numeros_disponiveis[current_idx - 1]
                await self.update_photo(interaction)
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em prev_page_callback: {e}")
            traceback.print_exc()
    
    async def next_page_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            if not self.numeros_disponiveis:
                return
            
            current_idx = self.numeros_disponiveis.index(self.current_page) if self.current_page in self.numeros_disponiveis else 0
            
            if current_idx < len(self.numeros_disponiveis) - 1:
                self.current_page = self.numeros_disponiveis[current_idx + 1]
                await self.update_photo(interaction)
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em next_page_callback: {e}")
            traceback.print_exc()
    
    async def voltar_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = MenuVisualizacaoView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="📍 Visualização de Bases",
                    description="Escolha uma opção:",
                    colour=Colour.blurple(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar_callback fotos: {e}")
            traceback.print_exc()
    
    async def update_photo(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            self.update_buttons()
            base = next((b for b in bases if b.numero == self.current_page), None)
            
            if not base or base.status != "livre":
                await interaction.response.edit_message(
                    embed=Embed(
                        title="❌ Erro",
                        description=f"Base {self.current_page} não disponível.",
                        colour=Colour.red()
                    ),
                    view=self,
                    attachments=[]
                )
                return
            
            posicao = self.numeros_disponiveis.index(self.current_page) + 1
            total = len(self.numeros_disponiveis)
            # Para usuários comuns, não mostra nomes
            mostrar_nome = has_admin_role(interaction)
            embed, file = await criar_embed_com_foto(base, posicao, total, 
                                                    mostrar_cds=False, mostrar_nome=mostrar_nome)
            
            if file:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em update_photo: {e}")
            traceback.print_exc()


class AdminFotosTodasView(SafeView):
    """View para navegar entre todas as fotos no menu ADM."""
    def __init__(self, current_page: int = 1):
        super().__init__(timeout=180)
        self.current_page = current_page
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Botão Anterior
        prev_button = ui.Button(
            label="◀️ Anterior", 
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page == 1)
        )
        prev_button.callback = self.prev_page_callback
        self.add_item(prev_button)
        
        # Botão Próximo
        next_button = ui.Button(
            label="Próximo ▶️", 
            style=discord.ButtonStyle.primary,
            disabled=(self.current_page == TOTAL_BASES)
        )
        next_button.callback = self.next_page_callback
        self.add_item(next_button)
        
        # Botão Voltar
        voltar_button = ui.Button(
            label="↩️ Voltar", 
            style=discord.ButtonStyle.secondary
        )
        voltar_button.callback = self.voltar_callback
        self.add_item(voltar_button)
    
    async def prev_page_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            self.current_page -= 1
            await self.update_photo(interaction)
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em prev_page_callback ADM: {e}")
            traceback.print_exc()
    
    async def next_page_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            self.current_page += 1
            await self.update_photo(interaction)
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em next_page_callback ADM: {e}")
            traceback.print_exc()
    
    async def voltar_callback(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            view = AdminMenuView()
            await interaction.response.edit_message(
                embed=Embed(
                    title="⚙️ Menu Administrativo",
                    description="Escolha uma opção:",
                    colour=Colour.dark_green(),
                ),
                view=view,
                attachments=[]
            )
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em voltar_callback ADM: {e}")
            traceback.print_exc()
    
    async def update_photo(self, interaction: Interaction):
        try:
            # Verificação de segurança
            if interaction.response.is_done():
                return
            
            self.update_buttons()
            base = next((b for b in bases if b.numero == self.current_page), None)
            
            if not base:
                await interaction.response.edit_message(
                    embed=Embed(
                        title="❌ Erro",
                        description=f"Base {self.current_page} não encontrada.",
                        colour=Colour.red()
                    ),
                    view=self,
                    attachments=[]
                )
                return
            
            embed, file = await criar_embed_com_foto(base, self.current_page, TOTAL_BASES, 
                                                    mostrar_cds=True, mostrar_nome=True)
            
            if file:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[])
        except discord.errors.NotFound:
            # Interação expirada, ignore
            pass
        except Exception as e:
            print(f"Erro em update_photo ADM: {e}")
            traceback.print_exc()


# -------------------------------------------------
#  Modais
# -------------------------------------------------
class BaseActionModal(ui.Modal):
    """Modal base para ações nas bases."""
    def __init__(self, title: str, target_status: str):
        super().__init__(title=title, timeout=None)
        self.target_status = target_status
        
        self.numero_base = ui.TextInput(
            label="Número da Base (1-14)",
            placeholder="Ex.: 5",
            required=True,
            max_length=2
        )
        self.nome = ui.TextInput(
            label="Nome da Facção",
            placeholder="Ex.: QG do Dragão",
            required=True,
            max_length=50
        )
        self.data = ui.TextInput(
            label="Data e Hora (dd/mm/aaaa HH:MM)",
            placeholder="Ex.: 31/12/2025 14:30",
            required=True,
            max_length=16
        )
        self.responsavel = ui.TextInput(
            label="Responsável",
            placeholder="Seu nome ou responsável",
            required=True,
            max_length=50
        )
        
        self.add_item(self.numero_base)
        self.add_item(self.nome)
        self.add_item(self.data)
        self.add_item(self.responsavel)

    async def on_submit(self, interaction: Interaction):
        try:
            numero = int(self.numero_base.value)
            if numero < 1 or numero > TOTAL_BASES:
                await interaction.response.send_message(
                    f"❌ Número inválido. Use um número entre 1 e {TOTAL_BASES}.",
                    ephemeral=True
                )
                return
            
            base = next((b for b in bases if b.numero == numero), None)
            if not base:
                await interaction.response.send_message(f"❌ Base {numero} não encontrada.", ephemeral=True)
                return
            
            if base.status != "livre":
                await interaction.response.send_message(f"❌ Base {numero} já está {base.status}.", ephemeral=True)
                return
            
            # Salva histórico antes de mudar
            adicionar_historico(base, base.status, base.nome, base.data, 
                              base.responsavel, f"Status anterior: {base.status}")
            
            # Atualiza dados
            base.nome = self.nome.value
            base.data = self.data.value
            base.responsavel = self.responsavel.value
            base.status = self.target_status
            
            # Salva no banco de dados
            salvar_base(base)
            
            # Adiciona novo registro ao histórico
            adicionar_historico(base, self.target_status, self.nome.value, self.data.value, 
                              self.responsavel.value, f"Base {self.target_status}")
            
            status_emoji = "🟡" if self.target_status == "reservada" else "🔴"
            status_text = "reservada" if self.target_status == "reservada" else "ocupada"
            
            await interaction.response.send_message(
                f"✅ {status_emoji} Base **{numero}** marcada como **{status_text}**!\n"
                f"**Facção:** {base.nome}\n**Data/Hora:** {base.data}\n"
                f"**Coordenadas:** {base.cds}\n"
                f"**Responsável:** {base.responsavel}",
                ephemeral=True
            )
            
            atualizar_painel_principal()
                
        except ValueError:
            await interaction.response.send_message("❌ Por favor, insira um número válido para a base.", ephemeral=True)
        except Exception as e:
            print(f"Erro em BaseActionModal: {e}")
            try:
                await interaction.response.send_message("❌ Ocorreu um erro ao processar a ação.", ephemeral=True)
            except:
                pass


class OcuparBaseModal(BaseActionModal):
    def __init__(self):
        super().__init__(title="Ocupar Base", target_status="ocupada")


class ReservarBaseModal(BaseActionModal):
    def __init__(self):
        super().__init__(title="Reservar Base", target_status="reservada")


# -------------------------------------------------
#  NOVOS MODAIS PARA BASES RESERVADAS
# -------------------------------------------------
class OcuparBaseReservadaModal(ui.Modal, title="Ocupar Base Reservada"):
    """Modal para ocupar uma base que está reservada."""
    
    numero_base = ui.TextInput(
        label="Número da Base Reservada (1-14)",
        placeholder="Ex.: 5",
        required=True,
        max_length=2
    )
    nome = ui.TextInput(
        label="Nome da Facção (mesmo ou novo)",
        placeholder="Ex.: QG do Dragão",
        required=True,
        max_length=50
    )
    data = ui.TextInput(
        label="Data e Hora (dd/mm/aaaa HH:MM)",
        placeholder="Ex.: 31/12/2025 14:30",
        required=True,
        max_length=16
    )
    responsavel = ui.TextInput(
        label="Responsável",
        placeholder="Seu nome ou responsável",
        required=True,
        max_length=50
    )

    async def on_submit(self, interaction: Interaction):
        try:
            numero = int(self.numero_base.value)
            if numero < 1 or numero > TOTAL_BASES:
                await interaction.response.send_message(
                    f"❌ Número inválido. Use um número entre 1 e {TOTAL_BASES}.",
                    ephemeral=True
                )
                return
            
            base = next((b for b in bases if b.numero == numero), None)
            if not base:
                await interaction.response.send_message(f"❌ Base {numero} não encontrada.", ephemeral=True)
                return
            
            if base.status != "reservada":
                await interaction.response.send_message(
                    f"❌ Base {numero} não está reservada. Status atual: {base.status}",
                    ephemeral=True
                )
                return
            
            # Salva histórico antes de mudar
            adicionar_historico(base, base.status, base.nome, base.data, 
                              base.responsavel, f"Ocupação de base reservada")
            
            # Atualiza dados
            base.nome = self.nome.value
            base.data = self.data.value
            base.responsavel = self.responsavel.value
            base.status = "ocupada"
            
            # Salva no banco de dados
            salvar_base(base)
            
            # Adiciona novo registro ao histórico
            adicionar_historico(base, "ocupada", self.nome.value, self.data.value, 
                              self.responsavel.value, "Ocupação de base reservada")
            
            await interaction.response.send_message(
                f"✅ 🔴 Base **{numero}** (reservada) agora está **OCUPADA**!\n"
                f"**Facção:** {base.nome}\n**Data/Hora:** {base.data}\n"
                f"**Coordenadas:** {base.cds}\n"
                f"**Responsável:** {base.responsavel}",
                ephemeral=True
            )
            
            atualizar_painel_principal()
                
        except ValueError:
            await interaction.response.send_message("❌ Por favor, insira um número válido para a base.", ephemeral=True)
        except Exception as e:
            print(f"Erro em OcuparBaseReservadaModal: {e}")
            try:
                await interaction.response.send_message("❌ Ocorreu um erro ao processar a ação.", ephemeral=True)
            except:
                pass


class DisponibilizarBaseModal(ui.Modal, title="Disponibilizar Base Reservada"):
    """Modal para disponibilizar uma base reservada."""
    
    numero_base = ui.TextInput(
        label="Número da Base Reservada (1-14)",
        placeholder="Ex.: 5",
        required=True,
        max_length=2
    )
    data = ui.TextInput(
        label="Data e Hora da Disponibilização (dd/mm/aaaa HH:MM)",
        placeholder="Ex.: 31/12/2025 14:30",
        required=True,
        max_length=16
    )
    responsavel = ui.TextInput(
        label="Responsável pela Disponibilização",
        placeholder="Seu nome",
        required=True,
        max_length=50
    )
    motivo = ui.TextInput(
        label="Motivo da Disponibilização",
        placeholder="Ex.: Reserva cancelada, período expirado, etc.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: Interaction):
        try:
            numero = int(self.numero_base.value)
            if numero < 1 or numero > TOTAL_BASES:
                await interaction.response.send_message(
                    f"❌ Número inválido. Use um número entre 1 e {TOTAL_BASES}.",
                    ephemeral=True
                )
                return
            
            base = next((b for b in bases if b.numero == numero), None)
            if not base:
                await interaction.response.send_message(f"❌ Base {numero} não encontrada.", ephemeral=True)
                return
            
            if base.status != "reservada":
                await interaction.response.send_message(
                    f"❌ Base {numero} não está reservada. Status atual: {base.status}",
                    ephemeral=True
                )
                return
            
            # Salva histórico antes de mudar
            adicionar_historico(base, base.status, base.nome, base.data, 
                              base.responsavel, f"Disponibilização: {self.motivo.value}")
            
            # Remove dados da reserva
            base.status = "livre"
            base.nome = None
            base.data = None
            base.responsavel = None
            
            # Salva no banco de dados
            salvar_base(base)
            
            # Adiciona registro de disponibilização
            adicionar_historico(base, "livre", motivo=self.motivo.value, 
                              data=self.data.value, responsavel=self.responsavel.value)
            
            await interaction.response.send_message(
                f"✅ 🟢 Base **{numero}** (reservada) foi **DISPONIBILIZADA**!\n"
                f"**Motivo:** {self.motivo.value}\n"
                f"**Data/Hora da disponibilização:** {self.data.value}\n"
                f"**Coordenadas:** {base.cds}\n"
                f"**Responsável pela disponibilização:** {self.responsavel.value}",
                ephemeral=True
            )
            
            atualizar_painel_principal()
                
        except ValueError:
            await interaction.response.send_message("❌ Por favor, insira um número válido para a base.", ephemeral=True)
        except Exception as e:
            print(f"Erro em DisponibilizarBaseModal: {e}")
            try:
                await interaction.response.send_message("❌ Ocorreu um erro ao disponibilizar a base.", ephemeral=True)
            except:
                pass


class DesocuparBaseModal(ui.Modal, title="Desocupar Base"):
    numero_base = ui.TextInput(
        label="Número da Base a Desocupar (1-14)",
        placeholder="Ex.: 5",
        required=True,
        max_length=2
    )
    data = ui.TextInput(
        label="Data e Hora da Desocupação (dd/mm/aaaa HH:MM)",
        placeholder="Ex.: 31/12/2025 14:30",
        required=True,
        max_length=16
    )
    motivo = ui.TextInput(
        label="Motivo da Desocupação",
        placeholder="Ex.: Cancelamento, Período encerrado, etc.",
        required=True,
        style=discord.TextStyle.paragraph,
        max_length=500
    )

    async def on_submit(self, interaction: Interaction):
        try:
            numero = int(self.numero_base.value)
            if numero < 1 or numero > TOTAL_BASES:
                await interaction.response.send_message(
                    f"❌ Número inválido. Use um número entre 1 e {TOTAL_BASES}.",
                    ephemeral=True
                )
                return
            
            base = next((b for b in bases if b.numero == numero), None)
            if not base:
                await interaction.response.send_message(f"❌ Base {numero} não encontrada.", ephemeral=True)
                return
            
            if base.status != "ocupada":
                await interaction.response.send_message(
                    f"❌ Base {numero} não está ocupada. Status atual: {base.status}",
                    ephemeral=True
                )
                return
            
            # Salva histórico antes de mudar
            adicionar_historico(base, base.status, base.nome, base.data, 
                              base.responsavel, f"Desocupação: {self.motivo.value}")
            
            # Remove dados da ocupação
            base.status = "livre"
            base.nome = None
            base.data = None
            base.responsavel = None
            
            # Salva no banco de dados
            salvar_base(base)
            
            # Adiciona registro de desocupação
            adicionar_historico(base, "livre", motivo=self.motivo.value, 
                              data=self.data.value, responsavel=interaction.user.name)
            
            await interaction.response.send_message(
                f"✅ 🟢 Base **{numero}** desocupada com sucesso!\n"
                f"**Motivo:** {self.motivo.value}\n"
                f"**Data/Hora:** {self.data.value}\n"
                f"**Coordenadas:** {base.cds}\n"
                f"**Responsável pela desocupação:** {interaction.user.name}",
                ephemeral=True
            )
            
            atualizar_painel_principal()
                
        except ValueError:
            await interaction.response.send_message("❌ Por favor, insira um número válido para a base.", ephemeral=True)
        except Exception as e:
            print(f"Erro em DesocuparBaseModal: {e}")
            try:
                await interaction.response.send_message("❌ Ocorreu um erro ao desocupar a base.", ephemeral=True)
            except:
                pass


# -------------------------------------------------
#  Eventos
# -------------------------------------------------
@bot.event
async def on_ready():
    print(f"🤖 Bot conectado como {bot.user} (ID: {bot.user.id})")
    
    if not os.path.exists("fotos-base"):
        print("⚠️ Pasta 'fotos-base' não encontrada. Criando...")
        os.makedirs("fotos-base")
        print("✅ Pasta 'fotos-base' criada.")
    
    try:
        await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print("✅ Comandos slash sincronizados.")
    except Exception as e:
        print(f"❌ Erro ao sincronizar commands: {e}")
    
    # Apenas a MainView precisa ser registrada como persistente
    bot.add_view(MainView())
    print("✅ Views persistentes registradas.")

    channel = bot.get_channel(CANAL_VENDAS_ID)
    if channel:
        embed = get_embed_main()
        async for msg in channel.history(limit=200):
            if msg.author == bot.user and msg.embeds:
                await msg.edit(embed=embed, view=MainView())
                print(f"✅ Embed principal atualizado no canal #{channel.name}")
                break
        else:
            await channel.send(embed=embed, view=MainView())
            print(f"✅ Embed principal enviado no canal #{channel.name}")
    else:
        print("⚠️ Canal de vendas não encontrado.")


# -------------------------------------------------
#  Comandos slash
# -------------------------------------------------
@bot.tree.command(name="test", description="Mostra o embed principal (apenas admin)", guild=discord.Object(id=GUILD_ID))
async def test(interaction: Interaction):
    if not has_admin_role(interaction):
        await interaction.response.send_message(f"❌ É necessário ter o cargo <@&{CARGO_ADM_ID}>.", ephemeral=True)
        return
    await interaction.response.send_message(embed=get_embed_main(), view=MainView(), ephemeral=True)


@bot.tree.command(name="ver_base", description="Visualiza informações de uma base específica", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(numero="Número da base (1-14)")
async def ver_base(interaction: Interaction, numero: int):
    if numero < 1 or numero > TOTAL_BASES:
        await interaction.response.send_message(f"❌ Número inválido. Use 1-{TOTAL_BASES}.", ephemeral=True)
        return
    
    # Verifica se é ADM para mostrar CDS e nomes
    mostrar_cds = has_admin_role(interaction)
    mostrar_nome = has_admin_role(interaction)  # Nomes apenas para ADM
    embed, file, _ = get_base_info_embed(numero, mostrar_cds, mostrar_nome)
    if file:
        await interaction.response.send_message(embed=embed, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="status_bases", description="Mostra o status atual de todas as bases", guild=discord.Object(id=GUILD_ID))
async def status_bases(interaction: Interaction):
    # Verifica se é ADM para mostrar CDS e nomes
    mostrar_cds = has_admin_role(interaction)
    mostrar_nome = has_admin_role(interaction)
    
    embed = Embed(title="📊 Status das Bases", colour=Colour.purple())
    
    for base in bases:
        status_emoji = "🟢" if base.status == "livre" else "🔴" if base.status == "ocupada" else "🟡"
        info = f"{status_emoji} **Base {base.numero}** - {base.status.title()}"
        
        if mostrar_cds:
            info += f"\n   📍 **Coordenadas:** {base.cds}"
        
        if mostrar_nome and base.nome:
            info += f"\n   📛 **Facção:** {base.nome}"
        
        if base.data:
            info += f"\n   📅 **Data/Hora:** {base.data}"
        
        if base.responsavel and base.status in ["ocupada", "reservada"] and mostrar_nome:
            info += f"\n   👤 **Responsável:** {base.responsavel}"
        
        embed.add_field(name=f"Base {base.numero}", value=info, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="ver_fotos", description="Visualiza as fotos das bases disponíveis", guild=discord.Object(id=GUILD_ID))
async def ver_fotos(interaction: Interaction):
    # Verifica se é ADM para mostrar CDS e nomes
    mostrar_cds = has_admin_role(interaction)
    mostrar_nome = has_admin_role(interaction)
    
    if not mostrar_cds:  # Não-ADMs veem apenas bases disponíveis
        bases_disponiveis = [b for b in bases if b.status == "livre"]
        if not bases_disponiveis:
            await interaction.response.send_message("❌ Não há bases disponíveis no momento.", ephemeral=True)
            return
        
        primeira_base = bases_disponiveis[0]
        embed, file = await criar_embed_com_foto(primeira_base, 1, len(bases_disponiveis), 
                                                mostrar_cds=False, mostrar_nome=mostrar_nome)
        view = BasePhotosDisponiveisView(current_page=primeira_base.numero)
    else:  # ADMs veem todas as bases
        primeira_base = bases[0]
        embed, file = await criar_embed_com_foto(primeira_base, 1, TOTAL_BASES, 
                                                mostrar_cds=True, mostrar_nome=True)
        view = AdminFotosTodasView(current_page=1)
    
    if file:
        await interaction.response.send_message(embed=embed, view=view, file=file, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


@bot.tree.command(name="backup", description="Cria um backup do banco de dados (apenas admin)", guild=discord.Object(id=GUILD_ID))
async def backup(interaction: Interaction):
    if not has_admin_role(interaction):
        await interaction.response.send_message(f"❌ É necessário ter o cargo <@&{CARGO_ADM_ID}>.", ephemeral=True)
        return
    
    import shutil
    import datetime
    
    data_atual = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_bases_{data_atual}.db"
    
    try:
        shutil.copy2('bases.db', backup_file)
        await interaction.response.send_message(
            f"✅ Backup criado com sucesso!\n"
            f"Arquivo: `{backup_file}`\n"
            f"Tamanho: {os.path.getsize(backup_file) / 1024:.2f} KB",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(f"❌ Erro ao criar backup: {str(e)}", ephemeral=True)


# -------------------------------------------------
#  Inicia o bot
# -------------------------------------------------
if __name__ == "__main__":
    bot.run(TOKEN)
