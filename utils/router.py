from colorama import Fore, Style

def router(state):
    if state.conversation_complete:
        return "__end__"
    print(f"{Fore.MAGENTA}[ROUTER]{Style.RESET_ALL} Next: {state.next_action}")
    return state.next_action.replace("wait_for_user","human_input")
