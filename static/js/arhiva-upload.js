/** Extracted from arhiva_upload.html — no Django template vars */
var dropZone = document.getElementById('dropZone');
var fileInputMain = document.getElementById('fileInputMain');

dropZone.addEventListener('dragover', function(e) {
  e.preventDefault();
  dropZone.style.borderColor = '#c9a84c';
  dropZone.style.background = 'rgba(201,168,76,.05)';
});
dropZone.addEventListener('dragleave', function() {
  dropZone.style.borderColor = '#334155';
  dropZone.style.background = '#0f172a';
});
dropZone.addEventListener('drop', function(e) {
  e.preventDefault();
  dropZone.style.borderColor = '#334155';
  dropZone.style.background = '#0f172a';
  var files = e.dataTransfer.files;
  if (files.length > 0) {
    var dt = new DataTransfer();
    dt.items.add(files[0]);
    fileInputMain.files = dt.files;
    handleFile(fileInputMain);
  }
});

dropZone.addEventListener('click', function(e) {
  if (e.target.tagName !== 'INPUT' && e.target.tagName !== 'LABEL' && e.target.tagName !== 'BUTTON') {
    fileInputMain.click();
  }
});

function handleFile(input) {
  var file = input.files[0];
  if (!file) return;
  if (input.id !== 'fileInputMain') {
    var dt = new DataTransfer();
    dt.items.add(file);
    fileInputMain.files = dt.files;
  }
  document.getElementById('dropContent').style.display = 'none';
  document.getElementById('filePreview').style.display = 'block';
  document.getElementById('previewName').textContent = file.name;
  document.getElementById('previewSize').textContent = formatSize(file.size);
  dropZone.style.borderColor = '#c9a84c';
  dropZone.style.borderStyle = 'solid';
  var previewImg = document.getElementById('previewImage');
  if (file.type.startsWith('image/')) {
    var reader = new FileReader();
    reader.onload = function(ev) {
      previewImg.innerHTML = '<img src="' + ev.target.result + '" style="max-height:200px;max-width:100%;border-radius:8px;border:1px solid #334155">';
    };
    reader.readAsDataURL(file);
  } else if (file.name.endsWith('.pdf')) {
    previewImg.innerHTML = '<div style="font-size:4rem">&#128209;</div>';
  } else if (file.name.endsWith('.xml')) {
    previewImg.innerHTML = '<div style="font-size:4rem">&#128203;</div>';
  } else {
    previewImg.innerHTML = '<div style="font-size:4rem">&#128196;</div>';
  }
}

function clearFile() {
  fileInputMain.value = '';
  document.getElementById('dropContent').style.display = 'block';
  document.getElementById('filePreview').style.display = 'none';
  document.getElementById('previewImage').innerHTML = '';
  dropZone.style.borderColor = '#334155';
  dropZone.style.borderStyle = 'dashed';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024*1024) return (bytes/1024).toFixed(1) + ' KB';
  return (bytes/(1024*1024)).toFixed(1) + ' MB';
}

document.getElementById('uploadForm').addEventListener('submit', function(e) {
  var mainInput = document.getElementById('fileInputMain');
  var camInput = document.getElementById('fileInputCamera');
  if (!mainInput.files.length && !camInput.files.length) {
    e.preventDefault();
    dropZone.style.borderColor = '#ef4444';
    dropZone.style.animation = 'shake .3s ease';
    setTimeout(function(){ dropZone.style.borderColor = '#334155'; }, 1000);
    fenixToast('Molimo odaberite datoteku za upload.', 'warning');
    return;
  }
  document.getElementById('progressSection').style.display = 'block';
  document.getElementById('submitBtn').disabled = true;
  document.getElementById('btnText').textContent = 'Saljem...';
  document.getElementById('btnIcon').textContent = '\u231B';
  var bar = document.getElementById('progressBar');
  var step2 = document.getElementById('step2');
  var step3 = document.getElementById('step3');
  setTimeout(function() { bar.style.width = '50%'; step2.style.color = '#c9a84c'; }, 200);
  setTimeout(function() { bar.style.width = '75%'; step2.textContent = '\u2461 Prijenos \u2713'; step3.style.color = '#c9a84c'; }, 1500);
});
