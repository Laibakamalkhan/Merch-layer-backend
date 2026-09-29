def choose_index(title,labels):
    print(f"\n{title}\n")
    for index,label in enumerate(labels,start=1):print(f"{index}. {label}")
    while True:
        value=input("\nSelect: ").strip()
        if value.isdigit():
            index=int(value)-1
            if 0<=index<len(labels):return index
        print("Invalid selection.")
