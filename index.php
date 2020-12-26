<?php

$url = "http://mhooge.com:5000/intfar";

$redir = "";
if ($_SERVER["REQUEST_URI"] != "/intfar/") {
    $redir = $url."/".(explode("/", $_SERVER["REQUEST_URI"], 3)[2]);
}
else {
    $redir = $url;
}

file_put_contents("log.txt", print_r($redir, true) . "\n", FILE_APPEND);

header("Location: " . $redir);
?>