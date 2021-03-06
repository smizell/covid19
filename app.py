import csv
import dataclasses
import datetime
import os
import pathlib
import shutil
import subprocess
import typing
import frontmatter
import markdown
import jinja2


BUILD_DIR = './build'
CONTENT_DIR = './content'
LAYOUTS_DIR = './layouts'
STATIC_DIR = './static'
DATA_DIR = './data'


@dataclasses.dataclass
class Document:
    dir_name: str
    file_name: str
    info: frontmatter.Post


@dataclasses.dataclass
class Context:
    data: dict
    docs: typing.List[Document]


def load_docs():
    docs = []
    for dir_name, _, file_names in os.walk(CONTENT_DIR):
        for file_name in file_names:
            info = frontmatter.load(os.path.join(dir_name, file_name))
            docs.append(Document(dir_name, file_name, info))
    return docs


def load_data():
    data = {}
    for file_name in os.listdir(DATA_DIR):
        # Allow for skipping files to load
        if file_name.startswith('_'):
            continue
        data_name, ext = file_name.split('.')
        if ext == 'csv':
            with open(os.path.join(DATA_DIR, file_name)) as f:
                data[data_name] = list(csv.DictReader(f))
    return data


def render(context):
    loader = jinja2.FileSystemLoader(searchpath=LAYOUTS_DIR)
    template_env = jinja2.Environment(loader=loader)
    templates = {
        # 'main': self.template_env.get_template('main.jinja2'),
        'page': template_env.get_template('page.jinja2'),
    } 

    for doc in context.docs:
        # Markdown uses the page template
        if doc.file_name.endswith('.md'):
            doc.info.content = markdown.markdown(doc.info.content)
            doc.file_name = doc.file_name.replace('.md', '.html')
            doc.info.content = templates['page'].render(context=context, doc=doc)

        # Jinja2 files will render as themselves
        # There is no need to use a page template as the `extends` tag
        # can be used to load other templates
        if doc.file_name.endswith('.jinja2'):
            template = template_env.from_string(doc.info.content)
            doc.file_name = doc.file_name.replace('.jinja2', '.html')
            doc.info.content = template.render(context=context, doc=doc)


def prepare(docs):
    for doc in docs:
        doc.dir_name = doc.dir_name.replace('./content', './build')
        if doc.file_name.endswith('.html') and doc.file_name != 'index.html':
            final_dir_name = '.'.join(doc.file_name.split('.')[:-1])
            doc.dir_name = os.path.join(doc.dir_name, final_dir_name)
            doc.file_name = 'index.html'


def persist(docs):
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.mkdir(BUILD_DIR)

    # This support static files in the STATIC_DIR
    shutil.copytree(STATIC_DIR, os.path.join(BUILD_DIR, STATIC_DIR))

    # Persist each doc into the build directory
    # It will use whatever file name is there, so docs need to be prepared
    # and rendered by this point.
    for doc in docs:
        if os.path.exists(doc.dir_name) == False:
            pathlib.Path(doc.dir_name).mkdir(parents=True, exist_ok=True)
        full_path = os.path.join(doc.dir_name, doc.file_name)
        with open(full_path, 'w+') as f:
            f.write(doc.info.content)


def set_last_modified(docs):
    for doc in docs:
        relative_path = os.path.join(doc.dir_name, doc.file_name)
        last_modified_output = subprocess.check_output(['git', 'log', '-1', '--format="%ad"', '--', relative_path])
        if last_modified_output:
            last_modified_text = last_modified_output.decode("utf-8").strip()[1:-1]
            # Example Tue Mar 17 22:30:27 2020 -0500
            last_modified = datetime.datetime.strptime(last_modified_text, "%a %b %d %H:%M:%S %Y %z")
            doc.info['last_modified_date'] = last_modified
            doc.info['last_modified'] = last_modified.strftime('%B %d, %Y at %I:%M %p')


def build():
    docs = load_docs()
    data = load_data()
    context = Context(data=data, docs=docs)
    set_last_modified(docs)
    render(context)
    prepare(docs)
    persist(docs)


if __name__ == '__main__':
    print(f'Building site from {BUILD_DIR}')
    build()
