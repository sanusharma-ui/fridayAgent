# # test_terminal.py
# from backend.services.task_manager import process_input

# print("Neo Assistant (Terminal Mode)")
# print("Type 'exit' to quit.\n")

# while True:
#     user_input = input("You: ")
#     if user_input.lower() in ["exit", "quit"]:
#         print("Neo: Goodbye Boss!")
#         break
    
#     reply = process_input(user_input)
#     print("Neo:", reply)
from backend.services.task_manager import process_input

print("Neo Assistant (Friday AI)")
print("Type 'exit' to quit.\n")

while True:
    user_input = input("You: ")
    if user_input.lower() in ["exit", "quit"]:
        print("Neo: Goodbye Boss!")
        break

    reply = process_input(user_input)
    print("Neo:", reply)
