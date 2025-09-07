# Simple TUI using Rich (Windows-friendly). Optional extra-credit UI.
# pip install rich
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
from client.stdio_client import StdioClient

console = Console()

def main():
    console.print("[bold cyan]BearingPro-MCP TUI[/bold cyan]")
    client = StdioClient()
    try:
        while True:
            console.print("\n[bold]Menu[/bold]: 1) catalog_list  2) select_bearing  3) verify_point  4) ping  0) exit")
            choice = Prompt.ask("Choose", choices=["1","2","3","4","0"], default="1")
            if choice == "0":
                break
            if choice == "1":
                resp = client.call("catalog_list", {})
                table = Table(title="Catalog")
                table.add_column("Model"); table.add_column("Type"); table.add_column("C_N")
                for it in resp["result"]["items"]:
                    table.add_row(it["model"], it["type"], str(it["C_N"]))
                console.print(table)
            elif choice == "2":
                Fr = float(Prompt.ask("Fr_N", default="3500"))
                Fa = float(Prompt.ask("Fa_N", default="1200"))
                rpm = float(Prompt.ask("rpm", default="1800"))
                target = float(Prompt.ask("L10h_target", default="12000"))
                rel = int(Prompt.ask("reliability_percent", default="90"))
                temp = float(Prompt.ask("temperature_C", default="40"))
                lub = Prompt.ask("lubrication", default="grease")
                params = {"Fr_N":Fr,"Fa_N":Fa,"rpm":rpm,"L10h_target":target,
                          "reliability_percent":rel,"temperature_C":temp,"lubrication":lub}
                resp = client.call("select_bearing", params)
                console.print(resp)
            elif choice == "3":
                model = Prompt.ask("model", default="NTN_6205C3")
                Fr = float(Prompt.ask("Fr_N", default="3000"))
                Fa = float(Prompt.ask("Fa_N", default="800"))
                rpm = float(Prompt.ask("rpm", default="1500"))
                rel = int(Prompt.ask("reliability_percent", default="90"))
                temp = float(Prompt.ask("temperature_C", default="40"))
                lub = Prompt.ask("lubrication", default="grease")
                target = Prompt.ask("L10h_target (optional)", default="")
                params = {"model":model,"Fr_N":Fr,"Fa_N":Fa,"rpm":rpm,
                          "reliability_percent":rel,"temperature_C":temp,"lubrication":lub}
                if target.strip():
                    params["L10h_target"] = float(target)
                resp = client.call("verify_point", params)
                console.print(resp)
            else:
                resp = client.call("ping", {})
                console.print(resp)
    finally:
        client.close()

if __name__ == "__main__":
    main()
