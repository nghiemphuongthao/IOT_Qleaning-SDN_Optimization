import time, json, os
SHARED = "../shared"

def collect_loop():
    while True:
        # read state files if Ryu dumps them; here demo: look for state.json
        p = os.path.join(SHARED, "last_state.json")
        if os.path.exists(p):
            st = json.load(open(p))
            print("Collected state:", st.get('timestamp'))
        time.sleep(1)

if __name__ == '__main__':
    collect_loop()
