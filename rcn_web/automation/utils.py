from urllib.parse import urljoin


def automation_get_storage_data(data):
    collected = []
    for i in data:
        st = i["storage"]
        ind = i["indicies"]
        d = st.get()
        collected.extend([d[j] for j in ind])

    return collected


def automation_get_storage_links(data):
    collected = []
    for i in data:
        st = i["storage"]
        ind = i["indicies"]
        d = st.get()
        app_url = st.parent_container.url
        collected.extend([urljoin(app_url, d[j]["path"][1:]) for j in ind])

    return collected
