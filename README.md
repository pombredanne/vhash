vhash
=====

vhash is a tool to detect similar videos using [Average Hash](http://www.hackerfactor.com/blog/index.php?/archives/432-Looks-Like-It.html).

## Usage

* **Generate vhash.** In this example, vhash will be named `video.vh1` and put besides video.mp4.

    ```
    ./vhash.py gen video.mp4
    ```

* **Compare two videos.** If vhash was generated, it will compare directly without regenerate the vhash. If vhash wasn't generated, it will be generated automatically.

    ```
    ./vhash.py match video1.mp4 video2.mp4
    ```
