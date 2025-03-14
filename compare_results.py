import os
import re
import pandas as pd

def extract_top1_acc(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()
        last_line = lines[-1]
        match = re.search(r'top-1 test acc: ([0-9.]+)', last_line)
        if match:
            return float(match.group(1))
    return None

def get_all_results(folder_path):
    results = []
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.txt'):
                file_path = os.path.join(root, file)
                top1_acc = extract_top1_acc(file_path)
                if top1_acc is not None:
                    results.append((root, file, top1_acc))
    return results

def main():
    folders = ['results', 'bert_results', 'bert_results_false']
    all_results = []

    for folder in folders:
        folder_results = get_all_results(folder)
        all_results.extend(folder_results)

    df = pd.DataFrame(all_results, columns=['Folder', 'File', 'Top-1 Test Acc'])
    print("All Results:")
    print(df)

    best_results = df.loc[df.groupby('Folder')['Top-1 Test Acc'].idxmax()]
    print("\nBest Results:")
    print(best_results)

if __name__ == "__main__":
    main()