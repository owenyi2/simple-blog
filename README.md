Write articles from Obsidian inside `./simple_blog`

From root, run `bash build/convert.sh`
- This internally creates a folder `build/md_ready` and calls `preprocess.py`

This also generates a folder `./site`

From `./site` run `python3 -m http.server 8080` to test out the site.

Deploy by 

```
git checkout gh-pages
git reset --hard
cp -r ./site/* .
rm -rf site
git add .
git commit -m "deploy"
git push 
```
