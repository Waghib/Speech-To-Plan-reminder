document.addEventListener('DOMContentLoaded', function() {
    const actionButton = document.getElementById('actionButton');
    const output = document.getElementById('output');

    actionButton.addEventListener('click', function() {
        output.textContent = 'Button clicked at: ' + new Date().toLocaleTimeString();
    });
});
